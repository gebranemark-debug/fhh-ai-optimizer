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

import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

# Make ``backend`` importable whether we're launched as
# "uvicorn backend.ai_model.api:app" (package import) or "python
# backend/ai_model/api.py" (file import).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend import data as fhh_data  # noqa: E402


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root() -> dict:
    return {
        "service": "fhh-ai-optimizer",
        "version": "v1.1",
        "contract": "API_CONTRACT.md v1.1",
        "endpoints": [
            "/machines",
            "/machines/{machine_id}",
            "/machines/{machine_id}/risk-score",
            "/machines/{machine_id}/predictions",
            "/alerts",
            "/alerts/{alert_id}",
            "/kpis/overview",
        ],
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


@app.get("/machines/{machine_id}/maintenance-log")
def get_machine_maintenance_log(machine_id: str) -> dict:
    try:
        return fhh_data.get_maintenance_log(machine_id)
    except fhh_data.MachineNotFound:
        raise _machine_404(machine_id)


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
