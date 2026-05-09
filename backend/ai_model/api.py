"""FastAPI service exposing the FHH predictive-maintenance endpoints.

Endpoints follow ``docs/API_CONTRACT-2.md`` v1.1 verbatim — same paths,
same JSON keys, same enum values. All data access goes through
``backend.data``, which is the swap-point for the production Oracle ADW
connector. While the Codespace has no Postgres / TimescaleDB / parquet
yet, ``backend.data`` falls back to deterministic hardcoded values that
match the contract and keep the demo wired end-to-end.

Run:
    uvicorn backend.ai_model.api:app --reload --port 8000
"""

from __future__ import annotations

import hashlib
import os
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Make ``backend`` importable whether we're launched as
# "uvicorn backend.ai_model.api:app" (package import) or "python
# backend/ai_model/api.py" (file import).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend import data as fhh_data  # noqa: E402
from backend.ai_model import chat_handler as chat_mod  # noqa: E402
from backend.auth import router as auth_router  # noqa: E402
from backend.auth.security import AppUser, get_current_user  # noqa: E402
from backend.chat import (  # noqa: E402
    router as chat_router,
    conversation_history_for_model,
    ensure_conversation_for_user,
    persist_assistant_turn,
    persist_user_turn,
)
from backend.maintenance import router as maintenance_router  # noqa: E402
from backend.postgres.db import session_scope  # noqa: E402

import time as _time
from collections import deque as _deque


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FHH AI Optimizer — Predictive Maintenance API",
    version="1.1",
    description="Endpoints conform to docs/API_CONTRACT-2.md v1.1.",
)


# -- CORS --------------------------------------------------------------------
# Allowed origins are configurable via the FHH_CORS_ALLOWED_ORIGINS env var
# (comma-separated). Defaults cover prod Vercel + local Vite/CRA dev. The
# regex matches Vercel preview deploys (fhh-ai-optimizer-<sha>.vercel.app).
_DEFAULT_CORS_ORIGINS = [
    "https://fhh-ai-optimizer.vercel.app",
    "http://localhost:5173",
    "http://localhost:3000",
]
_cors_env = os.environ.get("FHH_CORS_ALLOWED_ORIGINS")
_allowed_origins = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else _DEFAULT_CORS_ORIGINS
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"^https://(fhh-ai-optimizer-[A-Za-z0-9-]+\.vercel\.app|[A-Za-z0-9-]+-\d+\.app\.github\.dev)$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# -- Path C feature routers --------------------------------------------------
# These take precedence over the legacy GET /machines/{id}/maintenance-log
# below by being registered first; the legacy handler has been removed.
app.include_router(auth_router)
app.include_router(maintenance_router)
app.include_router(chat_router)


# -- Startup clock -----------------------------------------------------------
# Captured at import. /health subtracts from monotonic() for uptime so the
# value is robust to wall-clock changes (NTP corrections, container moves).
_APP_START_TIME = _time.monotonic()


@app.exception_handler(HTTPException)
async def _http_exception_handler(_request, exc: HTTPException):
    """Match the contract's error envelope: {"error": {"code", "message", "status"}}."""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {
            "code": "internal_error",
            "message": str(exc.detail),
            "status": exc.status_code,
        }},
    )


def _machine_404(machine_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": {
            "code": "machine_not_found",
            "message": f"No machine exists with ID '{machine_id}'.",
            "status": 404,
        }},
    )


def _alert_404(alert_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": {
            "code": "internal_error",
            "message": f"No alert exists with ID '{alert_id}'.",
            "status": 404,
        }},
    )


def _sensor_404(machine_id: str, sensor_type: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": {
            "code": "sensor_not_found",
            "message": f"No sensor '{sensor_type}' exists on machine '{machine_id}'.",
            "status": 404,
        }},
    )


def _component_404(machine_id: str, component_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": {
            "code": "component_not_found",
            "message": (
                f"No component '{component_id}' exists on machine "
                f"'{machine_id}'."
            ),
            "status": 404,
        }},
    )


def _component_failure_window_hours(score: int) -> int:
    """Monotonically decreasing window-to-failure as score rises. The
    bands match the contract's tier thresholds (24-72h critical, 72-
    168h warning, 168-720h watch, 720+h healthy) and the formula is
    deterministic so a given score always maps to the same window."""
    if score >= 76:    # critical: 24-72 hours
        return max(24, 72 - (score - 76) * 2)
    if score >= 51:    # warning: 72-168 hours (3-7 days)
        return max(72, 168 - (score - 51) * 4)
    if score >= 26:    # watch: 168-720 hours (1-4 weeks)
        return max(168, 720 - (score - 26) * 23)
    return max(720, 8760 - score * 322)  # healthy: 720+ hours


def _top_contributing_sensors(machine_id: str, component_id: str) -> list[dict]:
    """Return up to 3 sensors most relevant to (machine, component) with
    deterministic contribution percentages summing to 92-99%. Anomalous
    sensors rank ahead of normal ones so the answer reflects the live
    state; ties broken on sensor_type so the result is reproducible.
    Components with fewer than 3 sensors are padded with the next-most-
    anomalous sensors from elsewhere on the same machine."""
    try:
        sensors = fhh_data.get_sensors(machine_id)["readings"]
    except fhh_data.MachineNotFound:
        return []

    own = [s for s in sensors if s["component_id"] == component_id]
    own.sort(key=lambda s: (not s["is_anomaly"], s["sensor_type"]))

    if len(own) < 3:
        others = [s for s in sensors if s["component_id"] != component_id]
        others.sort(key=lambda s: (not s["is_anomaly"], s["sensor_type"]))
        own.extend(others[: 3 - len(own)])

    top = own[:3]
    if not top:
        return []

    # Stable seed: same machine+component → same percentages every call.
    seed = int(hashlib.md5(f"{machine_id}:{component_id}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    total = rng.randint(92, 99)
    first = rng.randint(50, 65)
    # Cap second so third stays >= 5 even if total is low and first is high.
    second_max = max(20, total - first - 5)
    second = rng.randint(20, max(20, min(30, second_max)))
    third = total - first - second

    pcts = [first, second, third][: len(top)]
    return [
        {"sensor_type": s["sensor_type"], "contribution_percent": pcts[i]}
        for i, s in enumerate(top)
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

# Routes that don't belong to a contract module (status, docs, etc.) and
# are excluded from the root summary's module breakdown.
_META_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


def _classify_route(path: str) -> Optional[str]:
    """Map a route path to its contract module bucket. Returns None for
    meta routes (root, health, docs) so they don't appear in the summary."""
    if path in _META_PATHS:
        return None
    if path.startswith("/kpis/"):
        # Both /kpis/overview and /kpis/cost-savings live under the
        # contract's "CROSS-CUTTING ENDPOINTS" section.
        return "cross_cutting"
    if path.startswith("/machines") or path.startswith("/alerts"):
        return "module_1_maintenance"
    if (
        path.startswith("/products")
        or path.startswith("/markets")
        or path.startswith("/forecast")
        or path.startswith("/demand")
    ):
        return "module_2_demand"
    if path.startswith("/chat"):
        return "module_3_chat"
    return None


def _now_iso_utc() -> str:
    """Contract canonical ISO timestamp — no ms, Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@app.get("/health")
def health() -> dict:
    """Liveness probe for deploy platforms (Railway / Render / Fly.io).
    Hot path — must respond in <50ms. No model load, no Anthropic call,
    no data-layer reads."""
    return {
        "status": "ok",
        "service": "fhh-ai-optimizer",
        "version": "1.1",
        "uptime_seconds": int(_time.monotonic() - _APP_START_TIME),
        "timestamp": _now_iso_utc(),
    }


@app.get("/")
def root() -> dict:
    """Service summary: enumerate currently-registered routes, grouped
    by contract module, so the listing can never drift from the actual
    app surface."""
    # Local import keeps the global namespace clean and avoids importing
    # internal FastAPI types until the root route is actually hit.
    from fastapi.routing import APIRoute

    buckets: dict[str, list[str]] = {
        "module_1_maintenance": [],
        "module_2_demand": [],
        "module_3_chat": [],
        "cross_cutting": [],
    }
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        bucket = _classify_route(route.path)
        if bucket is None:
            continue
        # Strip HEAD (FastAPI auto-adds it for GET routes); show only the
        # methods a client would actually call.
        for method in sorted((route.methods or set()) - {"HEAD"}):
            buckets[bucket].append(f"{method} {route.path}")
    for endpoints in buckets.values():
        endpoints.sort()

    return {
        "service": "FHH AI Optimizer",
        "version": "1.1",
        "description": (
            "Predictive maintenance + demand forecasting for Fine Hygienic "
            "Holding's Valmet DCT 200TS tissue lines."
        ),
        "contract": "API_CONTRACT.md v1.1",
        "modules": {
            mod: {"endpoints": len(eps), "endpoints_list": eps}
            for mod, eps in buckets.items()
        },
        "docs": "/docs",
        "health": "/health",
        "openapi": "/openapi.json",
        "github": "https://github.com/gebranemark-debug/fhh-ai-optimizer",
    }


@app.get("/machines")
def list_machines() -> dict:
    return fhh_data.get_machines()


@app.get("/machines/{machine_id}")
def get_machine(machine_id: str) -> dict:
    try:
        return fhh_data.get_machine(machine_id)
    except fhh_data.MachineNotFound:
        raise _machine_404(machine_id)


@app.get("/machines/{machine_id}/risk-score")
def get_machine_risk_score(machine_id: str) -> dict:
    try:
        return fhh_data.get_risk_score(machine_id)
    except fhh_data.MachineNotFound:
        raise _machine_404(machine_id)


@app.get("/machines/{machine_id}/predictions")
def get_machine_predictions(machine_id: str) -> dict:
    try:
        return fhh_data.get_predictions(machine_id)
    except fhh_data.MachineNotFound:
        raise _machine_404(machine_id)


@app.get("/machines/{machine_id}/components")
def get_machine_components(machine_id: str) -> dict:
    try:
        return fhh_data.get_components(machine_id)
    except fhh_data.MachineNotFound:
        raise _machine_404(machine_id)


@app.get("/machines/{machine_id}/components/{component_id}/risk-score")
def get_component_risk_score(machine_id: str, component_id: str) -> dict:
    """Component-level risk score with the top 3 contributing sensors —
    closes literal 100% contract coverage for Module 1."""
    try:
        comps = fhh_data.get_components(machine_id)
    except fhh_data.MachineNotFound:
        raise _machine_404(machine_id)

    comp = next(
        (c for c in comps["components"] if c["component_id"] == component_id),
        None,
    )
    if comp is None:
        raise _component_404(machine_id, component_id)

    score = int(comp["risk_score"])
    return {
        "machine_id": machine_id,
        "component_id": component_id,
        "score": score,
        "tier": comp["risk_tier"],
        "predicted_failure_window_hours": _component_failure_window_hours(score),
        "top_contributing_sensors": _top_contributing_sensors(machine_id, component_id),
        "last_updated": _now_iso_utc(),
    }


@app.get("/machines/{machine_id}/sensors")
def get_machine_sensors(machine_id: str) -> dict:
    try:
        return fhh_data.get_sensors(machine_id)
    except fhh_data.MachineNotFound:
        raise _machine_404(machine_id)


@app.get("/machines/{machine_id}/alarms")
def get_machine_alarms(
    machine_id: str,
    limit: int = Query(50, ge=1, le=200),
    severity: Optional[str] = Query(None, pattern="^(info|warning|critical)$"),
) -> dict:
    try:
        return fhh_data.get_alarms(machine_id, limit=limit, severity=severity)
    except fhh_data.MachineNotFound:
        raise _machine_404(machine_id)


# GET /machines/{id}/maintenance-log is now served by backend.maintenance.router,
# which merges analytics (parquet) + user-written (Postgres) entries.


@app.get("/machines/{machine_id}/sensors/{sensor_type}/history")
def get_machine_sensor_history(
    machine_id: str,
    sensor_type: str,
    window: str = Query("24h", pattern="^(1h|24h|7d|30d)$"),
    aggregation: str = Query("hourly", pattern="^(raw|hourly|daily)$"),
) -> dict:
    try:
        return fhh_data.get_sensor_history(machine_id, sensor_type, window, aggregation)
    except fhh_data.MachineNotFound:
        raise _machine_404(machine_id)
    except fhh_data.SensorNotFound:
        raise _sensor_404(machine_id, sensor_type)


@app.get("/alerts")
def list_alerts(
    severity: Optional[str] = Query(None, pattern="^(info|warning|critical)$"),
    machine_id: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    sort: str = Query("severity", pattern="^(severity|created_at|risk_score)$"),
) -> dict:
    return fhh_data.get_alerts(
        severity=severity,
        machine_id=machine_id,
        acknowledged=acknowledged,
        sort=sort,
    )


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str) -> dict:
    try:
        return fhh_data.get_alert(alert_id)
    except fhh_data.AlertNotFound:
        raise _alert_404(alert_id)


@app.get("/kpis/overview")
def kpis_overview() -> dict:
    return fhh_data.get_kpis_overview()


@app.get("/kpis/cost-savings")
def kpis_cost_savings(
    window: str = Query("ytd", pattern="^(mtd|qtd|ytd|all)$"),
) -> dict:
    return fhh_data.get_cost_savings(window)


@app.get("/products")
def list_products() -> dict:
    return fhh_data.get_products()


@app.get("/markets")
def list_markets() -> dict:
    return fhh_data.get_markets()


def _product_404(sku: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": {
            "code": "sku_not_found",
            "message": f"No product exists with SKU '{sku}'.",
            "status": 404,
        }},
    )


def _market_404(market_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": {
            "code": "invalid_request",
            "message": f"No market exists with ID '{market_id}'.",
            "status": 404,
        }},
    )


@app.get("/demand/anomalies")
def list_demand_anomalies() -> dict:
    return fhh_data.get_demand_anomalies()


@app.get("/demand/seasonality")
def get_demand_seasonality(
    sku: str,
    market: Optional[str] = None,
) -> dict:
    try:
        return fhh_data.get_seasonality(sku, market)
    except fhh_data.ProductNotFound:
        raise _product_404(sku)
    except fhh_data.MarketNotFound:
        raise _market_404(market or "")


@app.get("/forecast")
def get_forecast(
    sku: str,
    market: str,
    horizon_months: int = Query(6, ge=1, le=12),
) -> dict:
    try:
        return fhh_data.get_forecast(sku, market, horizon_months)
    except fhh_data.ProductNotFound:
        raise _product_404(sku)
    except fhh_data.MarketNotFound:
        raise _market_404(market)


class ScenarioBody(BaseModel):
    type: str = Field(pattern="^(seasonality_shift|price_change|competitor_entry|supply_disruption)$")
    event: Optional[str] = None
    magnitude_percent: Optional[float] = None


class ForecastScenarioRequest(BaseModel):
    sku: str
    market: str
    horizon_months: int = Field(6, ge=1, le=12)
    scenario: ScenarioBody


@app.post("/forecast/scenario")
def post_forecast_scenario(body: ForecastScenarioRequest) -> dict:
    try:
        return fhh_data.get_forecast_scenario(
            sku=body.sku,
            market=body.market,
            horizon_months=body.horizon_months,
            scenario=body.scenario.model_dump(),
        )
    except fhh_data.ProductNotFound:
        raise _product_404(body.sku)
    except fhh_data.MarketNotFound:
        raise _market_404(body.market)
    except fhh_data.ScenarioValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {
                "code": "validation_error",
                "message": str(exc),
                "status": 422,
            }},
        )


# ---------------------------------------------------------------------------
# Module 3 — chat assistant
# ---------------------------------------------------------------------------

@app.get("/chat/suggested-prompts")
def chat_suggested_prompts(
    current_page: Optional[str] = Query(None, pattern="^(overview|machine_detail|alerts|demand_forecast)$"),
    current_machine_id: Optional[str] = None,
    current_sku: Optional[str] = None,
) -> dict:
    return fhh_data.get_suggested_prompts(
        current_page=current_page,
        current_machine_id=current_machine_id,
        current_sku=current_sku,
    )


# GET / DELETE /chat/conversations/{id} are now served by backend.chat.router,
# which scopes conversations to the signed-in user via Postgres app schema.


# -- POST /chat -------------------------------------------------------------

# Simple in-memory rate limit: max N requests per window seconds across
# the whole process. Plenty for the demo and trivially swappable for
# Redis later. Keyed globally because the contract notes "too many chat
# requests" without per-user scoping.
_CHAT_RATE_MAX_REQUESTS = 30
_CHAT_RATE_WINDOW_SECONDS = 60
_CHAT_RATE_TIMESTAMPS: "_deque[float]" = _deque()


def _check_chat_rate_limit() -> None:
    now = _time.monotonic()
    cutoff = now - _CHAT_RATE_WINDOW_SECONDS
    # Drop expired entries from the left.
    while _CHAT_RATE_TIMESTAMPS and _CHAT_RATE_TIMESTAMPS[0] < cutoff:
        _CHAT_RATE_TIMESTAMPS.popleft()
    if len(_CHAT_RATE_TIMESTAMPS) >= _CHAT_RATE_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail={"error": {
                "code": "rate_limited",
                "message": (
                    f"Too many chat requests. Limit is "
                    f"{_CHAT_RATE_MAX_REQUESTS} per "
                    f"{_CHAT_RATE_WINDOW_SECONDS}s window."
                ),
                "status": 429,
            }},
        )
    _CHAT_RATE_TIMESTAMPS.append(now)


def _reset_chat_rate_limit() -> None:
    """For tests — drop the rolling window."""
    _CHAT_RATE_TIMESTAMPS.clear()


# One handler instance per process. Lazy-construct so the import doesn't
# require ANTHROPIC_API_KEY (e.g. for tests that don't hit /chat).
_CHAT_HANDLER: Optional[chat_mod.ChatHandler] = None


def _get_chat_handler() -> chat_mod.ChatHandler:
    global _CHAT_HANDLER
    if _CHAT_HANDLER is None:
        _CHAT_HANDLER = chat_mod.ChatHandler()
    return _CHAT_HANDLER


def _reset_chat_handler() -> None:
    """For tests — drop the cached handler so the next request rebuilds
    it (e.g. after env var changes)."""
    global _CHAT_HANDLER
    _CHAT_HANDLER = None


def _chat_unavailable(message: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"error": {
            "code": "chat_unavailable",
            "message": message,
            "status": 503,
        }},
    )


def _model_unavailable(message: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"error": {
            "code": "model_unavailable",
            "message": message,
            "status": 503,
        }},
    )


class ChatContext(BaseModel):
    current_page: Optional[str] = Field(None, pattern="^(overview|machine_detail|alerts|demand_forecast)$")
    current_machine_id: Optional[str] = None
    current_component_id: Optional[str] = None
    current_sku: Optional[str] = None
    current_market: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    context: Optional[ChatContext] = None


@app.post("/chat")
def post_chat(
    body: ChatRequest,
    user: AppUser = Depends(get_current_user),
) -> dict:
    # 0. Rate limit: 429 envelope if too many recent requests.
    _check_chat_rate_limit()

    # 1. Resolve conversation + load prior history while the session is open.
    #    The user's message is persisted in the same transaction so even if
    #    Anthropic fails, the input is in the conversation log.
    with session_scope() as s:
        conv = ensure_conversation_for_user(
            s,
            user_id=user.id,
            conversation_id=body.conversation_id,
            first_message=body.message,
        )
        history = conversation_history_for_model(s, conv.id)
        persist_user_turn(s, conv.id, body.message)
        cid = str(conv.id)

    # 2. Run the model (no DB session held during the network call so the
    #    pool isn't tied up while Anthropic streams).
    handler = _get_chat_handler()
    context = body.context.model_dump() if body.context else None
    try:
        result = handler.run(message=body.message, history=history, context=context)
    except chat_mod.UnknownToolError as exc:
        raise _model_unavailable(str(exc))
    except chat_mod.ChatUnavailableError as exc:
        raise _chat_unavailable(str(exc))

    # 3. Persist the assistant reply with data_sources_used metadata. Trigger
    #    chat_messages_touch_conversation auto-bumps conversations.updated_at.
    with session_scope() as s:
        persist_assistant_turn(
            s,
            uuid.UUID(cid),
            result["reply"],
            data_sources_used=result.get("data_sources_used"),
        )

    return {
        "conversation_id": cid,
        "reply": result["reply"],
        "data_sources_used": result.get("data_sources_used", []),
        "suggested_followups": result.get("suggested_followups", []),
        "timestamp": fhh_data._now_iso(),
    }
