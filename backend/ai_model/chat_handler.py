"""Anthropic-backed chat handler for the FHH AI Optimizer.

Wraps the Anthropic SDK + tool-use loop. Each tool is an HTTP call back
into the FHH backend's own endpoints — the chat is just another client
of the API, matching the architectural intent in API_CONTRACT-2.md
("chat ... gives Claude the other endpoints in this contract as tools").

The ANTHROPIC_API_KEY is read from backend/.env (loaded via python-dotenv
when present). The chat endpoint surfaces a graceful 503 envelope if the
key is missing or the API is unreachable.

Public surface:
    ChatHandler(base_url, api_key, model, http_client)
        .run(message, history, context) -> {
            "reply": str,
            "data_sources_used": list[str],   # endpoint paths Claude called
            "suggested_followups": list[str], # 3 strings
        }

    ChatUnavailableError — raised for any Anthropic-side failure (missing
    key, rate limit, transport error). Caught in api.py and translated to
    503 chat_unavailable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import httpx


# -- Optional dotenv autoload -----------------------------------------------

try:
    from dotenv import load_dotenv
    _ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH)
except ImportError:
    # python-dotenv is in requirements.txt but the handler still works
    # without it as long as the env vars are set some other way.
    pass


# -- Defaults & constants ---------------------------------------------------

def _resolve_base_url() -> str:
    """Resolve the URL the chat handler uses for its self-targeted HTTP
    tool calls. Precedence:
      1. ``FHH_INTERNAL_BASE_URL`` — explicit override (any deployment).
      2. ``PORT`` — Railway/Render-style. Build ``http://localhost:$PORT``
         since the chat handler runs in the same container as the API.
      3. ``http://127.0.0.1:8000`` — local dev default."""
    explicit = os.environ.get("FHH_INTERNAL_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    port = os.environ.get("PORT")
    if port:
        return f"http://localhost:{port}"
    return "http://127.0.0.1:8000"


_DEFAULT_BASE_URL = _resolve_base_url()
_DEFAULT_MODEL = "claude-sonnet-4-6"
_MAX_TOOL_ROUNDS = 5
_MAX_OUTPUT_TOKENS = 1024
_FOLLOWUP_TOKENS = 250


# -- Tool registry ----------------------------------------------------------

# Each tool maps to one HTTP call. ``_http`` carries:
#   method      - "GET" (all current tools are read-only)
#   path        - URL template; {placeholders} are substituted from path_params
#   path_params - args that go into the URL template (required)
#   query_params- args that become ?key=value (optional, copied if present)

TOOLS: list[dict] = [
    {
        "name": "get_machines",
        "description": (
            "List all 4 paper machines in the FHH fleet with their current "
            "risk_score (0-100), risk_tier (healthy|watch|warning|critical), "
            "status (running|idle|maintenance|offline), current_speed_mpm, "
            "current_oee_percent, and active_alerts_count. Call this for any "
            "fleet-wide question or to compare machines."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "_http": {"method": "GET", "path": "/machines", "path_params": [], "query_params": []},
    },
    {
        "name": "get_machine",
        "description": (
            "Get detailed info for one machine by id (location, model, install "
            "date, current status, OEE, risk_score, risk_tier, active alerts). "
            "Use when the user asks about a specific machine."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"machine_id": {"type": "string", "description": "One of: al-nakheel, al-bardi, al-sindian, al-snobar."}},
            "required": ["machine_id"],
        },
        "_http": {"method": "GET", "path": "/machines/{machine_id}", "path_params": ["machine_id"], "query_params": []},
    },
    {
        "name": "get_machine_risk_score",
        "description": (
            "Get the machine-level aggregate risk score for one machine: "
            "score (0-100), tier, highest_risk_component_id, last_updated. "
            "Use to quickly answer 'what's the risk on machine X?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"machine_id": {"type": "string"}},
            "required": ["machine_id"],
        },
        "_http": {"method": "GET", "path": "/machines/{machine_id}/risk-score", "path_params": ["machine_id"], "query_params": []},
    },
    {
        "name": "get_machine_components",
        "description": (
            "List the 6 components on a machine in line order (headbox, "
            "visconip, yankee, aircap, softreel, rewinder) with each "
            "component's risk_score, risk_tier, is_critical flag, "
            "expected_lifetime_hours, hours_since_last_maintenance, and "
            "last_maintenance_date. Use to identify which component is "
            "driving a machine's overall risk."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"machine_id": {"type": "string"}},
            "required": ["machine_id"],
        },
        "_http": {"method": "GET", "path": "/machines/{machine_id}/components", "path_params": ["machine_id"], "query_params": []},
    },
    {
        "name": "get_machine_predictions",
        "description": (
            "Get failure predictions across all 6 components on a machine: "
            "failure_probability (0.0-1.0), predicted_failure_window_hours, "
            "confidence (0.0-1.0), recommended_action. Use when the user "
            "asks 'what's about to fail?' or 'how long until X breaks?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"machine_id": {"type": "string"}},
            "required": ["machine_id"],
        },
        "_http": {"method": "GET", "path": "/machines/{machine_id}/predictions", "path_params": ["machine_id"], "query_params": []},
    },
    {
        "name": "get_machine_sensors",
        "description": (
            "Get the latest reading for all 14 sensors on a machine: "
            "sensor_type, component_id, value, unit, timestamp, is_anomaly. "
            "Use to identify which specific sensor reading is anomalous "
            "and driving a component's risk."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"machine_id": {"type": "string"}},
            "required": ["machine_id"],
        },
        "_http": {"method": "GET", "path": "/machines/{machine_id}/sensors", "path_params": ["machine_id"], "query_params": []},
    },
    {
        "name": "get_sensor_history",
        "description": (
            "Get time-series history for one sensor on one machine. Returns "
            "the sensor's normal_range plus a points array (timestamp, "
            "value, min, max). Use when the user asks how a reading has "
            "trended over time, or to show a chart of one sensor."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "machine_id":  {"type": "string"},
                "sensor_type": {"type": "string", "description": "e.g. 'yankee_vibration_bearing_3', 'yankee_surface_temp', 'aircap_inlet_temp'"},
                "window":      {"type": "string", "enum": ["1h", "24h", "7d", "30d"], "default": "24h"},
                "aggregation": {"type": "string", "enum": ["raw", "hourly", "daily"], "default": "hourly"},
            },
            "required": ["machine_id", "sensor_type"],
        },
        "_http": {
            "method": "GET",
            "path": "/machines/{machine_id}/sensors/{sensor_type}/history",
            "path_params": ["machine_id", "sensor_type"],
            "query_params": ["window", "aggregation"],
        },
    },
    {
        "name": "get_machine_alarms",
        "description": (
            "Get recent Valmet DCS alarm events for a machine. Each alarm "
            "has alarm_id, timestamp, severity (info|warning|critical), "
            "description, resolved_at (or null), downtime_minutes. Sorted "
            "newest-first. Use to recap what's been happening on a machine."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "machine_id": {"type": "string"},
                "limit":      {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
                "severity":   {"type": "string", "enum": ["info", "warning", "critical"]},
            },
            "required": ["machine_id"],
        },
        "_http": {
            "method": "GET",
            "path": "/machines/{machine_id}/alarms",
            "path_params": ["machine_id"],
            "query_params": ["limit", "severity"],
        },
    },
    {
        "name": "get_machine_maintenance_log",
        "description": (
            "Get the maintenance history for a machine: list of log entries "
            "(log_id, component_id, maintenance_type, date_performed, "
            "cost_usd, downtime_hours, technician, notes). Use when the user "
            "asks 'when was X last serviced?' or for a maintenance summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"machine_id": {"type": "string"}},
            "required": ["machine_id"],
        },
        "_http": {"method": "GET", "path": "/machines/{machine_id}/maintenance-log", "path_params": ["machine_id"], "query_params": []},
    },
    {
        "name": "get_alerts",
        "description": (
            "List active alerts across the fleet. Each alert has alert_id, "
            "machine_id, component_id, severity, risk_score, title, "
            "description, predicted_failure_window_hours, recommended_action, "
            "estimated_cost_if_unaddressed_usd, created_at, acknowledged. "
            "Includes counts_by_tier. Use for any alerts-page or 'what's "
            "the most urgent issue?' question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "severity":   {"type": "string", "enum": ["info", "warning", "critical"]},
                "machine_id": {"type": "string"},
                "sort":       {"type": "string", "enum": ["severity", "created_at", "risk_score"], "default": "severity"},
            },
            "required": [],
        },
        "_http": {
            "method": "GET",
            "path": "/alerts",
            "path_params": [],
            "query_params": ["severity", "machine_id", "sort"],
        },
    },
    {
        "name": "get_alert",
        "description": (
            "Get the full details of one alert by id. Use when the user "
            "drills into a specific alert (e.g. clicked a row in the alerts "
            "table)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"alert_id": {"type": "string", "description": "e.g. 'alt-2026-04-25-0017'"}},
            "required": ["alert_id"],
        },
        "_http": {"method": "GET", "path": "/alerts/{alert_id}", "path_params": ["alert_id"], "query_params": []},
    },
    {
        "name": "get_kpis_overview",
        "description": (
            "Get top-level dashboard KPIs: fleet_avg_oee_percent, "
            "active_critical_alerts, active_warning_alerts, "
            "predicted_downtime_prevented_hours_mtd, "
            "estimated_cost_saved_usd_mtd, machines_running, machines_total, "
            "last_updated. Use for any 'how's the fleet doing right now?' "
            "question."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "_http": {"method": "GET", "path": "/kpis/overview", "path_params": [], "query_params": []},
    },
    {
        "name": "get_cost_savings",
        "description": (
            "Get the ROI tracker — cumulative savings from predicted-and-"
            "prevented failures: total_predictions, predictions_acted_on, "
            "estimated_downtime_hours_prevented, estimated_cost_saved_usd, "
            "and a breakdown_by_machine. Use for any 'how much have we "
            "saved?' question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "window": {"type": "string", "enum": ["mtd", "qtd", "ytd", "all"], "default": "ytd"},
            },
            "required": [],
        },
        "_http": {"method": "GET", "path": "/kpis/cost-savings", "path_params": [], "query_params": ["window"]},
    },
]


# -- Errors -----------------------------------------------------------------

class ChatUnavailableError(RuntimeError):
    """Raised when the chat handler can't fulfil a request because of an
    Anthropic-side issue (missing API key, transport error, rate limit)."""


class UnknownToolError(RuntimeError):
    """Raised when Claude returns a tool name the handler doesn't recognise.
    Maps to 503 model_unavailable in the API layer."""


# -- Helpers ----------------------------------------------------------------

def _tool_definitions_for_anthropic() -> list[dict]:
    """Strip the internal _http key — Anthropic only needs name + description
    + input_schema."""
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
        for t in TOOLS
    ]


_TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}


def _format_path(path_template: str, args: dict, path_params: list[str]) -> str:
    out = path_template
    for p in path_params:
        if p not in args:
            raise UnknownToolError(f"missing required path param {p!r}")
        out = out.replace("{" + p + "}", str(args[p]))
    return out


def _build_system_prompt(context: Optional[dict]) -> str:
    base = (
        "You are an AI assistant for FHH (Fine Hygienic Holding) factory "
        "operations. The user runs paper-tissue production lines and asks "
        "you about machine health, alerts, maintenance, and demand forecasts.\n\n"
        "Rules:\n"
        "- Always use the provided tools to fetch live data. Never invent metrics, "
        "risk scores, or counts — call the appropriate tool first.\n"
        "- Reply concisely. 2-4 sentences for status answers; longer only when "
        "comparing or diagnosing. Use plain prose, not bullet points unless "
        "you're enumerating distinct items.\n"
        "- When citing a number, include its unit (e.g. '5.8 mm/s', '$480,000').\n"
        "- If a tool fails or returns an empty result, say so plainly rather "
        "than guessing.\n"
    )
    if not context:
        return base
    bits: list[str] = []
    if context.get("current_page"):
        bits.append(f"page='{context['current_page']}'")
    if context.get("current_machine_id"):
        bits.append(f"machine_id='{context['current_machine_id']}'")
    if context.get("current_component_id"):
        bits.append(f"component_id='{context['current_component_id']}'")
    if context.get("current_sku"):
        bits.append(f"sku='{context['current_sku']}'")
    if context.get("current_market"):
        bits.append(f"market='{context['current_market']}'")
    if not bits:
        return base
    return base + "\nThe user is currently looking at: " + ", ".join(bits) + "."


# -- Handler ----------------------------------------------------------------

class ChatHandler:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        self.base_url = base_url or os.environ.get("FHH_API_BASE_URL", _DEFAULT_BASE_URL)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or os.environ.get("FHH_CHAT_MODEL", _DEFAULT_MODEL)
        self._http_client = http_client  # injected for tests; lazy-created otherwise

    # -- HTTP tool execution ------------------------------------------------

    def _client(self) -> httpx.Client:
        if self._http_client is None:
            self._http_client = httpx.Client(base_url=self.base_url, timeout=10.0)
        return self._http_client

    def _execute_tool(self, name: str, args: dict) -> tuple[str, Any]:
        """Execute one tool call. Returns (rendered_path, result_json).
        ``rendered_path`` is what gets recorded in data_sources_used (the
        contract example uses paths without leading '/', so we strip)."""
        spec = _TOOLS_BY_NAME.get(name)
        if spec is None:
            raise UnknownToolError(f"unknown tool {name!r}")
        http = spec["_http"]
        path = _format_path(http["path"], args, http["path_params"])
        query = {k: args[k] for k in http["query_params"] if args.get(k) is not None}

        try:
            resp = self._client().request(http["method"], path, params=query)
        except httpx.HTTPError as exc:
            return path.lstrip("/"), {"error": f"transport error: {exc}"}

        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except Exception:
                payload = {"error": resp.text[:200]}
            return path.lstrip("/"), {"http_status": resp.status_code, **(payload if isinstance(payload, dict) else {"body": payload})}
        return path.lstrip("/"), resp.json()

    # -- Anthropic glue -----------------------------------------------------

    def _anthropic(self):
        if not self.api_key:
            raise ChatUnavailableError("ANTHROPIC_API_KEY is not set")
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ChatUnavailableError(f"anthropic SDK not installed: {exc}")
        return Anthropic(api_key=self.api_key)

    def _generate_followups(
        self,
        client,
        user_message: str,
        assistant_reply: str,
    ) -> list[str]:
        """Ask Claude for exactly 3 short follow-up questions in a small
        second call. Returns [] on any parse/transport failure — the
        absence of follow-ups shouldn't fail the main /chat response."""
        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=_FOLLOWUP_TOKENS,
                system=(
                    "You generate exactly 3 short follow-up questions a user "
                    "might ask next. Each under 12 words. No numbering, no "
                    "preamble, no markdown. Output strictly a JSON array of "
                    "3 strings, like: [\"...\",\"...\",\"...\"]"
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Question: {user_message}\n\n"
                        f"Answer: {assistant_reply}\n\n"
                        "Now produce 3 follow-ups."
                    ),
                }],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
            # Tolerate a trailing comment or surrounding prose by finding the bracketed list.
            start = text.find("[")
            end = text.rfind("]")
            if start == -1 or end == -1 or end <= start:
                return []
            arr = json.loads(text[start : end + 1])
            return [str(x).strip() for x in arr][:3] if isinstance(arr, list) else []
        except Exception:
            return []

    # -- Main entry ---------------------------------------------------------

    def run(
        self,
        message: str,
        history: list[dict],
        context: Optional[dict] = None,
    ) -> dict:
        """Run one chat turn. Returns {reply, data_sources_used,
        suggested_followups}. Raises ChatUnavailableError for any
        Anthropic-side failure."""
        client = self._anthropic()
        system = _build_system_prompt(context)
        tools = _tool_definitions_for_anthropic()

        # Conversation messages fed to Claude: prior turns + the new user msg.
        # Tool-result blocks accumulate here as we loop.
        messages: list[dict] = list(history) + [{"role": "user", "content": message}]
        data_sources_used: list[str] = []

        try:
            for _round in range(_MAX_TOOL_ROUNDS):
                response = client.messages.create(
                    model=self.model,
                    max_tokens=_MAX_OUTPUT_TOKENS,
                    system=system,
                    tools=tools,
                    messages=messages,
                )

                if response.stop_reason != "tool_use":
                    final_text = "".join(
                        b.text for b in response.content if getattr(b, "type", "") == "text"
                    ).strip()
                    followups = self._generate_followups(client, message, final_text)
                    return {
                        "reply": final_text,
                        "data_sources_used": data_sources_used,
                        "suggested_followups": followups,
                    }

                # Persist Claude's content blocks (text + tool_use) as the
                # assistant turn, then append our tool_result blocks.
                messages.append({"role": "assistant", "content": response.content})

                tool_results: list[dict] = []
                for block in response.content:
                    if getattr(block, "type", "") != "tool_use":
                        continue
                    tool_name = block.name
                    tool_args = dict(block.input) if isinstance(block.input, dict) else {}
                    path, result = self._execute_tool(tool_name, tool_args)
                    if path not in data_sources_used:
                        data_sources_used.append(path)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

                messages.append({"role": "user", "content": tool_results})

            # Hit the round cap without a final answer — return what we
            # have rather than 500'ing.
            return {
                "reply": (
                    "I gathered some data but ran out of analysis steps before "
                    "I could finalise an answer. Please ask a more specific "
                    "follow-up."
                ),
                "data_sources_used": data_sources_used,
                "suggested_followups": [],
            }

        except ChatUnavailableError:
            raise
        except UnknownToolError:
            raise
        except Exception as exc:
            # Anthropic SDK errors, network issues, etc. → 503 chat_unavailable.
            raise ChatUnavailableError(f"Anthropic call failed: {exc}") from exc
