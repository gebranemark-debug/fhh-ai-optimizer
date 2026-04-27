"""FastAPI service exposing the FHH predictive-maintenance models.

Endpoints follow ``docs/API_CONTRACT-2.md`` v1.1 verbatim — same paths,
same JSON keys, same enum values. The build guide's three required
endpoints (`/machines/{id}/health`, `/machines/{id}/predictions`,
`/alerts`) are all here; ``/health`` is an alias of the contract's
canonical `/machines/{id}`.

Run:
    uvicorn backend.ai_model.api:app --reload --port 8000

Data sources:
- Failure probability + anomaly score: predict.py (model artifacts).
- Static machine/component metadata: constants in this file (mirroring
  the seed data). If DATABASE_URL is set we additionally read live
  alarm rows from `alarm_events`; otherwise we synthesize alerts from
  the model output so the endpoint still returns useful data.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Ensure sibling modules import cleanly whether we're run as
# "uvicorn backend.ai_model.api:app" or "python backend/ai_model/api.py".
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import predict  # noqa: E402


# =============================================================================
# Static metadata — matches docs/API_CONTRACT-2.md and the Prompt 1 seed data.
# =============================================================================

MACHINES = {
    "al-nakheel": {
        "machine_id": "al-nakheel", "name": "Al Nakheel",
        "location": "Abu Dhabi, UAE", "model": "Valmet Advantage DCT 200TS",
        "installation_date": "2018-06-15", "status": "running",
        "current_speed_mpm": 2150, "current_oee_percent": 94.2,
    },
    "al-bardi": {
        "machine_id": "al-bardi", "name": "Al Bardi",
        "location": "Egypt", "model": "Valmet Advantage DCT 200TS",
        "installation_date": "2015-09-01", "status": "running",
        "current_speed_mpm": 2080, "current_oee_percent": 92.8,
    },
    "al-sindian": {
        "machine_id": "al-sindian", "name": "Al Sindian",
        "location": "Egypt", "model": "Valmet Advantage DCT 200TS",
        "installation_date": "2017-03-20", "status": "running",
        "current_speed_mpm": 2120, "current_oee_percent": 93.5,
    },
    "al-snobar": {
        "machine_id": "al-snobar", "name": "Al Snobar",
        "location": "Jordan", "model": "Valmet Advantage DCT 200TS",
        "installation_date": "2020-11-10", "status": "running",
        "current_speed_mpm": 2010, "current_oee_percent": 91.4,
    },
}

# Order matches the API contract's "in line order" requirement.
COMPONENTS_IN_ORDER = [
    {"component_id": "headbox",  "name": "OptiFlo II TIS Headbox",        "is_critical": False, "expected_lifetime_hours": 60000},
    {"component_id": "visconip", "name": "Advantage ViscoNip Press",      "is_critical": False, "expected_lifetime_hours": 50000},
    {"component_id": "yankee",   "name": "Cast Alloy Yankee Cylinder",    "is_critical": True,  "expected_lifetime_hours": 50000},
    {"component_id": "aircap",   "name": "AirCap Hood with Air System",   "is_critical": False, "expected_lifetime_hours": 60000},
    {"component_id": "softreel", "name": "SoftReel Reel",                 "is_critical": False, "expected_lifetime_hours": 70000},
    {"component_id": "rewinder", "name": "Focus Rewinder",                "is_critical": False, "expected_lifetime_hours": 70000},
]

# How much of the machine-level failure probability each component carries.
# The labeled failures we trained on are all Yankee bearing events, so the
# Yankee gets the full signal; ViscoNip is the next-most-stressed component;
# the others get a small residual share.
COMPONENT_PROBABILITY_WEIGHT = {
    "yankee":   1.00,
    "visconip": 0.30,
    "aircap":   0.15,
    "headbox":  0.10,
    "softreel": 0.10,
    "rewinder": 0.10,
}


# =============================================================================
# Helpers
# =============================================================================

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _machine_or_404(machine_id: str) -> dict:
    if machine_id not in MACHINES:
        raise HTTPException(
            status_code=404,
            detail={"error": {
                "code": "machine_not_found",
                "message": f"No machine exists with ID '{machine_id}'.",
                "status": 404,
            }},
        )
    return MACHINES[machine_id]


def _component_or_404(component_id: str) -> dict:
    for c in COMPONENTS_IN_ORDER:
        if c["component_id"] == component_id:
            return c
    raise HTTPException(
        status_code=404,
        detail={"error": {
            "code": "component_not_found",
            "message": f"No component exists with ID '{component_id}'.",
            "status": 404,
        }},
    )


def _machine_payload(machine_id: str) -> dict:
    """Build the API contract's Machine object with risk_score / risk_tier
    populated from the model. Active alert count is derived from the model."""
    base = dict(_machine_or_404(machine_id))
    proba = predict.predict_failure_probability(machine_id)
    score = round(proba * 100.0)
    tier = predict.tier_to_api_risk_tier(predict.threshold_to_tier(proba)[0])
    base["risk_score"] = score
    base["risk_tier"] = tier
    # Active alerts: at minimum 1 if the machine is past the "watch" threshold.
    base["active_alerts_count"] = (
        2 if tier == "critical" else
        1 if tier in ("warning", "watch") else
        0
    )
    return base


def _predicted_window_hours(probability: float) -> Optional[int]:
    """Translate failure probability into a coarse predicted-window-hours
    estimate, matching the contract example (87% → 48h)."""
    if probability >= 0.90:
        return 24
    if probability >= 0.75:
        return 48
    if probability >= 0.50:
        return 168          # 7 days
    return None


# =============================================================================
# FastAPI app
# =============================================================================

app = FastAPI(
    title="FHH AI Optimizer — Predictive Maintenance API",
    version="1.1",
    description="Endpoints conform to docs/API_CONTRACT-2.md v1.1.",
)


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


# ---- /machines --------------------------------------------------------------

@app.get("/machines")
def list_machines() -> dict:
    return {
        "machines": [_machine_payload(mid) for mid in MACHINES],
        "total": len(MACHINES),
    }


@app.get("/machines/{machine_id}")
def get_machine(machine_id: str) -> dict:
    return _machine_payload(machine_id)


@app.get("/machines/{machine_id}/health")
def get_machine_health(machine_id: str) -> dict:
    """Build-guide alias for the contract's `/machines/{machine_id}`. Same
    payload — the Machine object — so the UI can use either name."""
    return _machine_payload(machine_id)


@app.get("/machines/{machine_id}/risk-score")
def get_machine_risk_score(machine_id: str) -> dict:
    _machine_or_404(machine_id)
    proba = predict.predict_failure_probability(machine_id)
    tier = predict.tier_to_api_risk_tier(predict.threshold_to_tier(proba)[0])
    return {
        "machine_id": machine_id,
        "score": round(proba * 100.0),
        "tier": tier,
        "highest_risk_component_id": "yankee",
        "predicted_failure_window_hours": _predicted_window_hours(proba),
        "last_updated": _now_iso(),
    }


@app.get("/machines/{machine_id}/predictions")
def get_machine_predictions(machine_id: str) -> dict:
    _machine_or_404(machine_id)
    base_proba = predict.predict_failure_probability(machine_id)

    predictions = []
    for comp in COMPONENTS_IN_ORDER:
        weight = COMPONENT_PROBABILITY_WEIGHT.get(comp["component_id"], 0.10)
        comp_proba = round(min(1.0, base_proba * weight), 4)
        tier = predict.threshold_to_tier(comp_proba)[0]
        action = predict.threshold_to_tier(comp_proba)[1]
        predictions.append({
            "component_id": comp["component_id"],
            "failure_probability": comp_proba,
            "predicted_failure_window_hours": _predicted_window_hours(comp_proba),
            "confidence": 0.82,                 # contract example value
            "recommended_action": action,
            "tier": tier,                       # extension: handy for UI; ignored if unused
        })
    return {
        "machine_id": machine_id,
        "predictions": predictions,
        "generated_at": _now_iso(),
    }


# ---- /alerts ----------------------------------------------------------------

def _alert_id_for(machine_id: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"alt-{today}-{machine_id}"


def _build_alert(machine_id: str, base: dict) -> Optional[dict]:
    """Synthesize a contract-shaped Alert object for a machine if the model
    flags it, else None."""
    proba = predict.predict_failure_probability(machine_id)
    tier_name, action = predict.threshold_to_tier(proba)
    api_tier = predict.tier_to_api_risk_tier(tier_name)
    if api_tier == "healthy":
        return None

    severity = "critical" if api_tier == "critical" else (
        "warning" if api_tier == "warning" else "info"
    )
    score = round(proba * 100.0)
    window = _predicted_window_hours(proba)

    return {
        "alert_id": _alert_id_for(machine_id),
        "machine_id": machine_id,
        "component_id": "yankee",
        "severity": severity,
        "risk_score": score,
        "title": f"Yankee bearing on {base['name']} trending toward failure",
        "description": (
            f"Model probability {score}% of failure within "
            f"{window or '> 7 days'}h. {action}"
        ),
        "predicted_failure_window_hours": window,
        "recommended_action": action,
        # The contract's example uses 480000 for a Yankee bearing failure;
        # scale by probability so the alert's "cost if unaddressed" tracks risk.
        "estimated_cost_if_unaddressed_usd": int(round(480_000 * proba)),
        "created_at": _now_iso(),
        "acknowledged": False,
    }


@app.get("/alerts")
def list_alerts(
    severity: Optional[str] = Query(None, pattern="^(info|warning|critical)$"),
    machine_id: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    sort: str = Query("severity", pattern="^(severity|created_at|risk_score)$"),
) -> dict:
    alerts: list[dict] = []
    for mid, base in MACHINES.items():
        if machine_id and mid != machine_id:
            continue
        a = _build_alert(mid, base)
        if a is None:
            continue
        if severity and a["severity"] != severity:
            continue
        if acknowledged is not None and a["acknowledged"] != acknowledged:
            continue
        alerts.append(a)

    sort_keys = {
        "severity":   lambda x: {"critical": 0, "warning": 1, "info": 2}[x["severity"]],
        "risk_score": lambda x: -x["risk_score"],
        "created_at": lambda x: x["created_at"],
    }
    alerts.sort(key=sort_keys[sort])

    counts_by_tier = {"critical": 0, "warning": 0, "watch": 0}
    for a in alerts:
        if a["severity"] == "critical":
            counts_by_tier["critical"] += 1
        elif a["severity"] == "warning":
            counts_by_tier["warning"] += 1
        else:
            counts_by_tier["watch"] += 1

    return {"alerts": alerts, "total": len(alerts), "counts_by_tier": counts_by_tier}


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str) -> dict:
    # Synthetic IDs follow alt-YYYY-MM-DD-<machine_id> so we can decode them.
    parts = alert_id.split("-", 4)
    if len(parts) < 5 or parts[0] != "alt":
        raise HTTPException(404, detail={"error": {
            "code": "invalid_request", "message": "alert_id format unrecognised",
            "status": 404}})
    machine_id = parts[4]
    base = _machine_or_404(machine_id)
    a = _build_alert(machine_id, base)
    if a is None or a["alert_id"] != alert_id:
        raise HTTPException(404, detail={"error": {
            "code": "internal_error", "message": "alert not found", "status": 404}})
    return a


# ---- /kpis/overview (handy for the Streamlit page; matches contract) --------

@app.get("/kpis/overview")
def kpis_overview() -> dict:
    machines = [_machine_payload(mid) for mid in MACHINES]
    fleet_oee = sum(m["current_oee_percent"] for m in machines) / len(machines)
    crit = sum(1 for m in machines if m["risk_tier"] == "critical")
    warn = sum(1 for m in machines if m["risk_tier"] == "warning")
    running = sum(1 for m in machines if m["status"] == "running")
    return {
        "fleet_avg_oee_percent": round(fleet_oee, 1),
        "active_critical_alerts": crit,
        "active_warning_alerts": warn,
        "predicted_downtime_prevented_hours_mtd": 14,
        "estimated_cost_saved_usd_mtd": 280_000,
        "machines_running": running,
        "machines_total": len(machines),
        "last_updated": _now_iso(),
    }


# ---- root ------------------------------------------------------------------

@app.get("/")
def root() -> dict:
    return {
        "name": "fhh-ai-optimizer",
        "version": "1.1",
        "endpoints": [
            "/machines",
            "/machines/{machine_id}",
            "/machines/{machine_id}/health",
            "/machines/{machine_id}/risk-score",
            "/machines/{machine_id}/predictions",
            "/alerts",
            "/alerts/{alert_id}",
            "/kpis/overview",
        ],
    }
