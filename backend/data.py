"""Single data-access module for the FHH predictive-maintenance API.

This is the swap-point for the production Oracle ADW connector. Today it
reads from ``backend/timescale/features.parquet`` when available and
falls back to deterministic in-process values that match
``docs/API_CONTRACT-2.md`` v1.1 verbatim. Tomorrow, when integration
begins, the same public functions get rewired to talk to ADW — every
endpoint handler stays untouched.

Public surface (all return contract-shaped dicts):

    get_machines()                    -> {"machines": [...], "total": int}
    get_machine(machine_id)           -> Machine object
    get_risk_score(machine_id)        -> /risk-score payload
    get_predictions(machine_id)       -> /predictions payload
    get_alerts(filters...)            -> /alerts payload
    get_alert(alert_id)               -> Alert object
    get_kpis_overview()               -> /kpis/overview payload
    get_components(machine_id)        -> /components payload
    get_sensors(machine_id)           -> /sensors payload
    get_alarms(machine_id, ...)       -> /alarms payload
    get_maintenance_log(machine_id)   -> /maintenance-log payload
    get_sensor_history(...)           -> /sensors/{type}/history payload
    get_cost_savings(window)          -> /kpis/cost-savings payload
    get_products()                    -> /products payload
    get_markets()                     -> /markets payload
    get_demand_history(sku, market)   -> DataFrame for the forecast layer
    get_demand_anomalies()            -> /demand/anomalies payload
    get_seasonality(sku, market)      -> /demand/seasonality payload
    get_forecast(sku, market, h)      -> /forecast payload

Exceptions:
    MachineNotFound, AlertNotFound, SensorNotFound — caught in
    ``backend/ai_model/api.py`` and translated to the contract's 404
    error envelope.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Optional parquet load — runs once at import. If the file is missing (the
# Codespace doesn't have ETL output yet), every endpoint still works from
# the hardcoded fallback values below. When the parquet appears, lookups
# transparently start using it.
# ---------------------------------------------------------------------------

_FEATURES_PATH = Path(__file__).parent / "timescale" / "features.parquet"


def _try_load_features() -> Optional[pd.DataFrame]:
    if not _FEATURES_PATH.exists():
        return None
    try:
        return pd.read_parquet(_FEATURES_PATH)
    except Exception:
        return None


_FEATURES: Optional[pd.DataFrame] = _try_load_features()


def features_loaded() -> bool:
    """For diagnostics — True if features.parquet was read successfully."""
    return _FEATURES is not None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class MachineNotFound(KeyError):
    def __init__(self, machine_id: str):
        super().__init__(machine_id)
        self.machine_id = machine_id


class AlertNotFound(KeyError):
    def __init__(self, alert_id: str):
        super().__init__(alert_id)
        self.alert_id = alert_id


class SensorNotFound(KeyError):
    def __init__(self, machine_id: str, sensor_type: str):
        super().__init__(f"{machine_id}/{sensor_type}")
        self.machine_id = machine_id
        self.sensor_type = sensor_type


# ---------------------------------------------------------------------------
# Constants — values mirror frontend/app/src/mockData.js so the demo wires
# end-to-end without visual drift. Locations come from docs/fhh_machines_
# sensors.pdf; risk scores match the spec from the human in the loop.
# ---------------------------------------------------------------------------

MACHINE_MODEL = "Valmet Advantage DCT 200TS"

_MACHINES: list[dict] = [
    {
        "machine_id": "al-nakheel",
        "name": "Al Nakheel",
        "location": "Abu Dhabi, UAE",
        "model": MACHINE_MODEL,
        "installation_date": "2018-06-15",
        "status": "running",
        "current_speed_mpm": 2150,
        "current_oee_percent": 91.4,
        "risk_score": 87,
        "risk_tier": "critical",
    },
    {
        "machine_id": "al-bardi",
        "name": "Al Bardi",
        "location": "Tenth of Ramadan, Egypt",
        "model": MACHINE_MODEL,
        "installation_date": "2019-03-22",
        "status": "running",
        "current_speed_mpm": 2080,
        "current_oee_percent": 93.6,
        "risk_score": 67,
        "risk_tier": "warning",
    },
    {
        "machine_id": "al-sindian",
        "name": "Al Sindian",
        "location": "Sadat City, Egypt",
        "model": MACHINE_MODEL,
        "installation_date": "2020-09-08",
        "status": "maintenance",
        "current_speed_mpm": 0,
        "current_oee_percent": 0,
        "risk_score": 42,
        "risk_tier": "watch",
    },
    {
        "machine_id": "al-snobar",
        "name": "Al Snobar",
        "location": "Amman, Jordan",
        "model": MACHINE_MODEL,
        "installation_date": "2021-11-30",
        "status": "running",
        "current_speed_mpm": 2210,
        "current_oee_percent": 96.1,
        "risk_score": 18,
        "risk_tier": "healthy",
    },
]

# Component reference — order matches the contract's "in line order":
# headbox → visconip → yankee → aircap → softreel → rewinder.
COMPONENTS_IN_ORDER: list[dict] = [
    {"component_id": "headbox",  "name": "OptiFlo II TIS Headbox",     "is_critical": False, "expected_lifetime_hours": 60000},
    {"component_id": "visconip", "name": "Advantage ViscoNip Press",   "is_critical": False, "expected_lifetime_hours": 50000},
    {"component_id": "yankee",   "name": "Cast Alloy Yankee Cylinder", "is_critical": True,  "expected_lifetime_hours": 50000},
    {"component_id": "aircap",   "name": "AirCap Hood with Air System","is_critical": False, "expected_lifetime_hours": 60000},
    {"component_id": "softreel", "name": "SoftReel Reel",              "is_critical": False, "expected_lifetime_hours": 70000},
    {"component_id": "rewinder", "name": "Focus Rewinder",             "is_critical": False, "expected_lifetime_hours": 70000},
]

# Highest-risk component per machine — Yankee everywhere except al-sindian
# (in maintenance, currently servicing the rewinder per maintenance log).
_HIGHEST_RISK_COMPONENT: dict[str, str] = {
    "al-nakheel": "yankee",
    "al-bardi":   "yankee",
    "al-sindian": "rewinder",
    "al-snobar":  "yankee",
}

# Per-machine, per-component failure predictions. Verbatim parity with
# frontend/app/src/mockData.js > predictionsByMachine. al-sindian is in
# maintenance, so predictions are nulled until it returns to running.
_PREDICTIONS_BY_MACHINE: dict[str, list[dict]] = {
    "al-nakheel": [
        {"component_id": "headbox",  "failure_probability": 0.12,   "predicted_failure_window_hours": 2160, "confidence": 0.71, "recommended_action": "Continue normal operation. Routine inspection scheduled."},
        {"component_id": "visconip", "failure_probability": 0.3047, "predicted_failure_window_hours": 720,  "confidence": 0.74, "recommended_action": "Inspect felt run within 7 days. Consider felt change at next planned stop."},
        {"component_id": "yankee",   "failure_probability": 0.9998, "predicted_failure_window_hours": 24,   "confidence": 0.82, "recommended_action": "CRITICAL: Stop line immediately. Replace component now."},
        {"component_id": "aircap",   "failure_probability": 0.1432, "predicted_failure_window_hours": 360,  "confidence": 0.68, "recommended_action": "Re-tune burner during next 4-hour window. Verify gas pressure regulator."},
        {"component_id": "softreel", "failure_probability": 0.11,   "predicted_failure_window_hours": 1800, "confidence": 0.66, "recommended_action": "No action required. Continue monitoring."},
        {"component_id": "rewinder", "failure_probability": 0.10,   "predicted_failure_window_hours": 2400, "confidence": 0.69, "recommended_action": "No action required. Continue monitoring."},
    ],
    "al-bardi": [
        {"component_id": "headbox",  "failure_probability": 0.09,   "predicted_failure_window_hours": 2400, "confidence": 0.72, "recommended_action": "Continue normal operation."},
        {"component_id": "visconip", "failure_probability": 0.21,   "predicted_failure_window_hours": 960,  "confidence": 0.70, "recommended_action": "Monitor felt moisture trend. No immediate action."},
        {"component_id": "yankee",   "failure_probability": 0.4803, "predicted_failure_window_hours": 168,  "confidence": 0.75, "recommended_action": "Schedule PRV inspection within 7 days. Pull historian trend on PV-2102."},
        {"component_id": "aircap",   "failure_probability": 0.13,   "predicted_failure_window_hours": 1080, "confidence": 0.69, "recommended_action": "Continue normal operation."},
        {"component_id": "softreel", "failure_probability": 0.3214, "predicted_failure_window_hours": 504,  "confidence": 0.71, "recommended_action": "Recalibrate dancer load cell. Verify pneumatic supply pressure."},
        {"component_id": "rewinder", "failure_probability": 0.10,   "predicted_failure_window_hours": 1920, "confidence": 0.68, "recommended_action": "No action required."},
    ],
    "al-sindian": [
        {"component_id": "headbox",  "failure_probability": None, "predicted_failure_window_hours": None, "confidence": None, "recommended_action": "Awaiting next prediction run after machine returns to running state."},
        {"component_id": "visconip", "failure_probability": None, "predicted_failure_window_hours": None, "confidence": None, "recommended_action": "Awaiting next prediction run."},
        {"component_id": "yankee",   "failure_probability": None, "predicted_failure_window_hours": None, "confidence": None, "recommended_action": "Awaiting next prediction run."},
        {"component_id": "aircap",   "failure_probability": None, "predicted_failure_window_hours": None, "confidence": None, "recommended_action": "Awaiting next prediction run."},
        {"component_id": "softreel", "failure_probability": None, "predicted_failure_window_hours": None, "confidence": None, "recommended_action": "Awaiting next prediction run."},
        {"component_id": "rewinder", "failure_probability": None, "predicted_failure_window_hours": None, "confidence": None, "recommended_action": "Awaiting next prediction run."},
    ],
    "al-snobar": [
        {"component_id": "headbox",  "failure_probability": 0.04, "predicted_failure_window_hours": 4320, "confidence": 0.81, "recommended_action": "No action required."},
        {"component_id": "visconip", "failure_probability": 0.09, "predicted_failure_window_hours": 2880, "confidence": 0.78, "recommended_action": "Order replacement felt; schedule swap during next planned shutdown."},
        {"component_id": "yankee",   "failure_probability": 0.05, "predicted_failure_window_hours": 4080, "confidence": 0.83, "recommended_action": "No action required."},
        {"component_id": "aircap",   "failure_probability": 0.06, "predicted_failure_window_hours": 3840, "confidence": 0.79, "recommended_action": "No action required."},
        {"component_id": "softreel", "failure_probability": 0.07, "predicted_failure_window_hours": 3360, "confidence": 0.77, "recommended_action": "No action required."},
        {"component_id": "rewinder", "failure_probability": 0.04, "predicted_failure_window_hours": 4560, "confidence": 0.82, "recommended_action": "No action required."},
    ],
}

# 8 alerts — IDs, descriptions, recommended_actions, costs, timestamps and
# acknowledged flags match frontend/app/src/mockData.js exactly. This is
# the one alerts list the frontend can wire onto with no visual drift.
_ALERTS: list[dict] = [
    {
        "alert_id": "alt-2026-04-25-0017",
        "machine_id": "al-nakheel",
        "component_id": "yankee",
        "severity": "critical",
        "risk_score": 87,
        "title": "Bearing 3 vibration trending toward failure",
        "description": "Bearing 3 vibration RMS rising 0.4 mm/s/day for 11 days. Current reading 5.8 mm/s vs. 2-4 mm/s normal range. Predicted failure window: 24 hours.",
        "predicted_failure_window_hours": 24,
        "recommended_action": "CRITICAL: Stop line immediately. Replace component now.",
        "estimated_cost_if_unaddressed_usd": 480000,
        "created_at": "2026-04-25T08:15:00Z",
        "acknowledged": False,
    },
    {
        "alert_id": "alt-2026-04-25-0014",
        "machine_id": "al-nakheel",
        "component_id": "aircap",
        "severity": "warning",
        "risk_score": 71,
        "title": "AirCap inlet temperature drift above setpoint",
        "description": "AirCap inlet temperature trending +6 °C above setpoint over 72 h. Energy consumption up 4.1%. Likely burner tuning required.",
        "predicted_failure_window_hours": 240,
        "recommended_action": "Schedule burner re-tune during next 4-hour window. Verify gas pressure regulator.",
        "estimated_cost_if_unaddressed_usd": 62000,
        "created_at": "2026-04-24T22:40:00Z",
        "acknowledged": False,
    },
    {
        "alert_id": "alt-2026-04-25-0012",
        "machine_id": "al-nakheel",
        "component_id": "visconip",
        "severity": "warning",
        "risk_score": 64,
        "title": "Felt moisture above target — sheet quality at risk",
        "description": "ViscoNip felt moisture at 47.8% (target 35-45%). Drying load on Yankee elevated; softness index trending down.",
        "predicted_failure_window_hours": None,
        "recommended_action": "Inspect felt run; consider felt change at next planned stop.",
        "estimated_cost_if_unaddressed_usd": 38000,
        "created_at": "2026-04-24T17:05:00Z",
        "acknowledged": True,
    },
    {
        "alert_id": "alt-2026-04-24-0009",
        "machine_id": "al-bardi",
        "component_id": "yankee",
        "severity": "warning",
        "risk_score": 67,
        "title": "Steam pressure oscillation on Yankee header",
        "description": "Steam pressure oscillating ±0.6 bar around setpoint. Possible PRV stiction. Crepe quality variance up 12%.",
        "predicted_failure_window_hours": 168,
        "recommended_action": "Schedule PRV inspection within 7 days. Pull historian trend on PV-2102.",
        "estimated_cost_if_unaddressed_usd": 84000,
        "created_at": "2026-04-24T11:22:00Z",
        "acknowledged": False,
    },
    {
        "alert_id": "alt-2026-04-24-0007",
        "machine_id": "al-bardi",
        "component_id": "softreel",
        "severity": "warning",
        "risk_score": 58,
        "title": "Reel tension drift outside tolerance",
        "description": "SoftReel tension drifting low — 168 N/m vs. 180-220 normal. Risk of loose reels and break frequency increase.",
        "predicted_failure_window_hours": None,
        "recommended_action": "Recalibrate dancer load cell. Verify pneumatic supply pressure.",
        "estimated_cost_if_unaddressed_usd": 24000,
        "created_at": "2026-04-23T19:48:00Z",
        "acknowledged": False,
    },
    {
        "alert_id": "alt-2026-04-24-0005",
        "machine_id": "al-sindian",
        "component_id": "headbox",
        "severity": "info",
        "risk_score": 41,
        "title": "Stock temperature low at headbox during warm-up",
        "description": "Stock temperature reading 39 °C during scheduled warm-up. Within expected range for maintenance state.",
        "predicted_failure_window_hours": None,
        "recommended_action": "No action — informational. Will clear when machine returns to running state.",
        "estimated_cost_if_unaddressed_usd": 0,
        "created_at": "2026-04-23T08:10:00Z",
        "acknowledged": True,
    },
    {
        "alert_id": "alt-2026-04-23-0003",
        "machine_id": "al-sindian",
        "component_id": "rewinder",
        "severity": "warning",
        "risk_score": 49,
        "title": "Rewinder drive current spike pattern detected",
        "description": "Repeated current spikes on rewinder main drive — 12 events in 48 h. Bearing or coupling wear suspected.",
        "predicted_failure_window_hours": 336,
        "recommended_action": "Schedule vibration analysis at next planned stop (already in maintenance).",
        "estimated_cost_if_unaddressed_usd": 41000,
        "created_at": "2026-04-22T14:55:00Z",
        "acknowledged": False,
    },
    {
        "alert_id": "alt-2026-04-22-0002",
        "machine_id": "al-snobar",
        "component_id": "visconip",
        "severity": "info",
        "risk_score": 22,
        "title": "Routine felt life advisory — 18% remaining",
        "description": "Felt life model estimates 18% remaining (≈ 14 days at current load). No anomalies detected.",
        "predicted_failure_window_hours": None,
        "recommended_action": "Order replacement felt; schedule swap during next planned shutdown.",
        "estimated_cost_if_unaddressed_usd": 0,
        "created_at": "2026-04-22T07:30:00Z",
        "acknowledged": False,
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _machine_or_raise(machine_id: str) -> dict:
    for m in _MACHINES:
        if m["machine_id"] == machine_id:
            return m
    raise MachineNotFound(machine_id)


def _unacknowledged_alerts_for(machine_id: str) -> list[dict]:
    return [a for a in _ALERTS if a["machine_id"] == machine_id and not a["acknowledged"]]


# Severity -> counts_by_tier bucket. Per the contract's counts_by_tier
# example: critical | warning | watch. Info-severity alerts bucket into
# "watch" (informational / advisory tier).
_SEVERITY_TO_TIER_BUCKET = {
    "critical": "critical",
    "warning":  "warning",
    "info":     "watch",
}

_SEVERITY_SORT_RANK = {"critical": 0, "warning": 1, "info": 2}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _machine_payload(machine_id: str) -> dict:
    """Build a contract-shaped Machine object. ``active_alerts_count`` is
    derived from the live alerts list so it stays consistent if alerts move."""
    base = _machine_or_raise(machine_id)
    return {
        "machine_id": base["machine_id"],
        "name": base["name"],
        "location": base["location"],
        "model": base["model"],
        "installation_date": base["installation_date"],
        "status": base["status"],
        "current_speed_mpm": base["current_speed_mpm"],
        "current_oee_percent": base["current_oee_percent"],
        "risk_score": int(base["risk_score"]),
        "risk_tier": base["risk_tier"],
        "active_alerts_count": len(_unacknowledged_alerts_for(machine_id)),
    }


def get_machines() -> dict:
    machines = [_machine_payload(m["machine_id"]) for m in _MACHINES]
    return {"machines": machines, "total": len(machines)}


def get_machine(machine_id: str) -> dict:
    return _machine_payload(machine_id)


def get_risk_score(machine_id: str) -> dict:
    m = _machine_or_raise(machine_id)
    return {
        "machine_id": m["machine_id"],
        "score": int(m["risk_score"]),
        "tier": m["risk_tier"],
        "highest_risk_component_id": _HIGHEST_RISK_COMPONENT.get(m["machine_id"], "yankee"),
        "last_updated": _now_iso(),
    }


def get_predictions(machine_id: str) -> dict:
    _machine_or_raise(machine_id)
    preds = _PREDICTIONS_BY_MACHINE[machine_id]
    # Each prediction item is already in contract shape — copy so callers
    # can't mutate the module-level constant.
    return {
        "machine_id": machine_id,
        "predictions": [dict(p) for p in preds],
        "generated_at": _now_iso(),
    }


def get_alerts(
    severity: Optional[str] = None,
    machine_id: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    sort: str = "severity",
) -> dict:
    items = list(_ALERTS)
    if severity is not None:
        items = [a for a in items if a["severity"] == severity]
    if machine_id is not None:
        items = [a for a in items if a["machine_id"] == machine_id]
    if acknowledged is not None:
        items = [a for a in items if a["acknowledged"] is acknowledged]

    if sort == "severity":
        items.sort(key=lambda a: (_SEVERITY_SORT_RANK[a["severity"]], -a["risk_score"]))
    elif sort == "risk_score":
        items.sort(key=lambda a: -a["risk_score"])
    elif sort == "created_at":
        items.sort(key=lambda a: a["created_at"], reverse=True)
    else:
        # Defensive — api.py constrains the enum, but if some other caller
        # passes through, fall back to severity ordering.
        items.sort(key=lambda a: (_SEVERITY_SORT_RANK[a["severity"]], -a["risk_score"]))

    counts_by_tier = {"critical": 0, "warning": 0, "watch": 0}
    for a in items:
        bucket = _SEVERITY_TO_TIER_BUCKET[a["severity"]]
        counts_by_tier[bucket] += 1

    return {
        "alerts": [dict(a) for a in items],
        "total": len(items),
        "counts_by_tier": counts_by_tier,
    }


def get_alert(alert_id: str) -> dict:
    for a in _ALERTS:
        if a["alert_id"] == alert_id:
            return dict(a)
    raise AlertNotFound(alert_id)


def get_kpis_overview() -> dict:
    machines = [_machine_payload(m["machine_id"]) for m in _MACHINES]
    running = [m for m in machines if m["status"] == "running"]
    fleet_oee = (
        round(sum(m["current_oee_percent"] for m in running) / len(running), 1)
        if running
        else 0.0
    )
    active_critical = sum(
        1 for a in _ALERTS if a["severity"] == "critical" and not a["acknowledged"]
    )
    active_warning = sum(
        1 for a in _ALERTS if a["severity"] == "warning" and not a["acknowledged"]
    )
    return {
        "fleet_avg_oee_percent": fleet_oee,
        "active_critical_alerts": active_critical,
        "active_warning_alerts": active_warning,
        "predicted_downtime_prevented_hours_mtd": 14,
        "estimated_cost_saved_usd_mtd": 280000,
        "machines_running": len(running),
        "machines_total": len(machines),
        "last_updated": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Components & sensors — per-machine state mirroring frontend mockData.js for
# end-to-end parity. Static metadata (name, is_critical, expected_lifetime
# _hours) lives in COMPONENTS_IN_ORDER above; per-machine state is here.
# ---------------------------------------------------------------------------

# Anchor "today" so hours_since_last_maintenance is reproducible across runs.
_ANCHOR_TODAY = date(2026, 4, 25)

# Per-machine component health. Mirrors frontend/app/src/mockData.js >
# componentsByMachine. ``health_score`` (good = high) is inverted to the
# contract's ``risk_score`` (bad = high) at response time. al-sindian shows
# real values even though it's in maintenance — components keep their state,
# only sensor readings go to zero.
_COMPONENTS_BY_MACHINE: dict[str, list[dict]] = {
    "al-nakheel": [
        {"component_id": "headbox",  "health_score": 88, "tier": "healthy",  "last_service_date": "2026-02-14"},
        {"component_id": "visconip", "health_score": 64, "tier": "warning",  "last_service_date": "2025-11-08"},
        {"component_id": "yankee",   "health_score":  9, "tier": "critical", "last_service_date": "2024-09-12"},
        {"component_id": "aircap",   "health_score": 72, "tier": "watch",    "last_service_date": "2025-12-02"},
        {"component_id": "softreel", "health_score": 86, "tier": "healthy",  "last_service_date": "2026-01-20"},
        {"component_id": "rewinder", "health_score": 91, "tier": "healthy",  "last_service_date": "2026-03-05"},
    ],
    "al-bardi": [
        {"component_id": "headbox",  "health_score": 91, "tier": "healthy", "last_service_date": "2026-03-01"},
        {"component_id": "visconip", "health_score": 78, "tier": "watch",   "last_service_date": "2025-10-22"},
        {"component_id": "yankee",   "health_score": 58, "tier": "warning", "last_service_date": "2025-08-15"},
        {"component_id": "aircap",   "health_score": 84, "tier": "healthy", "last_service_date": "2025-12-10"},
        {"component_id": "softreel", "health_score": 69, "tier": "watch",   "last_service_date": "2025-11-28"},
        {"component_id": "rewinder", "health_score": 88, "tier": "healthy", "last_service_date": "2026-02-18"},
    ],
    "al-sindian": [
        {"component_id": "headbox",  "health_score": 82, "tier": "healthy", "last_service_date": "2026-01-10"},
        {"component_id": "visconip", "health_score": 75, "tier": "watch",   "last_service_date": "2025-12-15"},
        {"component_id": "yankee",   "health_score": 80, "tier": "healthy", "last_service_date": "2025-11-04"},
        {"component_id": "aircap",   "health_score": 79, "tier": "healthy", "last_service_date": "2026-02-20"},
        {"component_id": "softreel", "health_score": 71, "tier": "watch",   "last_service_date": "2025-10-30"},
        {"component_id": "rewinder", "health_score": 62, "tier": "warning", "last_service_date": "2025-09-18"},
    ],
    "al-snobar": [
        {"component_id": "headbox",  "health_score": 96, "tier": "healthy", "last_service_date": "2026-03-22"},
        {"component_id": "visconip", "health_score": 89, "tier": "healthy", "last_service_date": "2026-01-05"},
        {"component_id": "yankee",   "health_score": 94, "tier": "healthy", "last_service_date": "2025-11-30"},
        {"component_id": "aircap",   "health_score": 92, "tier": "healthy", "last_service_date": "2026-02-08"},
        {"component_id": "softreel", "health_score": 90, "tier": "healthy", "last_service_date": "2026-01-15"},
        {"component_id": "rewinder", "health_score": 95, "tier": "healthy", "last_service_date": "2026-03-10"},
    ],
}

# Per-machine current sensor readings (14 sensors). Mirrors frontend
# mockData.js > sensorsByMachine after makeSensors() resolution. al-sindian
# is in maintenance, so every value is 0, every reading non-anomalous, and
# the timestamp reflects the last reading before line stop.
_RUNNING_SENSOR_TIMESTAMP = "2026-04-28T09:30:00Z"
_MAINT_SENSOR_TIMESTAMP   = "2026-04-22T06:00:00Z"

_SENSORS_BY_MACHINE: dict[str, list[dict]] = {
    "al-nakheel": [
        {"sensor_type": "headbox_stock_consistency",  "component_id": "headbox",  "unit": "%",    "value": 0.32,  "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "headbox_jet_velocity",       "component_id": "headbox",  "unit": "m/s",  "value": 25.4,  "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "visconip_nip_load",          "component_id": "visconip", "unit": "kN/m", "value": 95,    "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "visconip_felt_moisture",     "component_id": "visconip", "unit": "%",    "value": 47.8,  "is_anomaly": True,  "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "yankee_surface_temp",        "component_id": "yankee",   "unit": "°C",   "value": 112.4, "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "yankee_steam_pressure",      "component_id": "yankee",   "unit": "bar",  "value": 9.6,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "yankee_vibration_bearing_3", "component_id": "yankee",   "unit": "mm/s", "value": 5.8,   "is_anomaly": True,  "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "aircap_inlet_temp",          "component_id": "aircap",   "unit": "°C",   "value": 496,   "is_anomaly": True,  "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "aircap_exhaust_humidity",    "component_id": "aircap",   "unit": "%",    "value": 38,    "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "softreel_tension",           "component_id": "softreel", "unit": "N/m",  "value": 198,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "softreel_drive_current",     "component_id": "softreel", "unit": "A",    "value": 142,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "rewinder_drive_current",     "component_id": "rewinder", "unit": "A",    "value": 88,    "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "rewinder_dancer_position",   "component_id": "rewinder", "unit": "mm",   "value": 24,    "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "qcs_basis_weight_cd_stddev", "component_id": "rewinder", "unit": "g/m²", "value": 0.8,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
    ],
    "al-bardi": [
        {"sensor_type": "headbox_stock_consistency",  "component_id": "headbox",  "unit": "%",    "value": 0.32,  "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "headbox_jet_velocity",       "component_id": "headbox",  "unit": "m/s",  "value": 25.4,  "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "visconip_nip_load",          "component_id": "visconip", "unit": "kN/m", "value": 95,    "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "visconip_felt_moisture",     "component_id": "visconip", "unit": "%",    "value": 41.2,  "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "yankee_surface_temp",        "component_id": "yankee",   "unit": "°C",   "value": 112.4, "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "yankee_steam_pressure",      "component_id": "yankee",   "unit": "bar",  "value": 10.7,  "is_anomaly": True,  "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "yankee_vibration_bearing_3", "component_id": "yankee",   "unit": "mm/s", "value": 3.1,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "aircap_inlet_temp",          "component_id": "aircap",   "unit": "°C",   "value": 478,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "aircap_exhaust_humidity",    "component_id": "aircap",   "unit": "%",    "value": 38,    "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "softreel_tension",           "component_id": "softreel", "unit": "N/m",  "value": 168,   "is_anomaly": True,  "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "softreel_drive_current",     "component_id": "softreel", "unit": "A",    "value": 142,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "rewinder_drive_current",     "component_id": "rewinder", "unit": "A",    "value": 88,    "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "rewinder_dancer_position",   "component_id": "rewinder", "unit": "mm",   "value": 24,    "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "qcs_basis_weight_cd_stddev", "component_id": "rewinder", "unit": "g/m²", "value": 0.8,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
    ],
    "al-sindian": [
        {"sensor_type": "headbox_stock_consistency",  "component_id": "headbox",  "unit": "%",    "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
        {"sensor_type": "headbox_jet_velocity",       "component_id": "headbox",  "unit": "m/s",  "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
        {"sensor_type": "visconip_nip_load",          "component_id": "visconip", "unit": "kN/m", "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
        {"sensor_type": "visconip_felt_moisture",     "component_id": "visconip", "unit": "%",    "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
        {"sensor_type": "yankee_surface_temp",        "component_id": "yankee",   "unit": "°C",   "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
        {"sensor_type": "yankee_steam_pressure",      "component_id": "yankee",   "unit": "bar",  "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
        {"sensor_type": "yankee_vibration_bearing_3", "component_id": "yankee",   "unit": "mm/s", "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
        {"sensor_type": "aircap_inlet_temp",          "component_id": "aircap",   "unit": "°C",   "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
        {"sensor_type": "aircap_exhaust_humidity",    "component_id": "aircap",   "unit": "%",    "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
        {"sensor_type": "softreel_tension",           "component_id": "softreel", "unit": "N/m",  "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
        {"sensor_type": "softreel_drive_current",     "component_id": "softreel", "unit": "A",    "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
        {"sensor_type": "rewinder_drive_current",     "component_id": "rewinder", "unit": "A",    "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
        {"sensor_type": "rewinder_dancer_position",   "component_id": "rewinder", "unit": "mm",   "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
        {"sensor_type": "qcs_basis_weight_cd_stddev", "component_id": "rewinder", "unit": "g/m²", "value": 0, "is_anomaly": False, "timestamp": _MAINT_SENSOR_TIMESTAMP},
    ],
    "al-snobar": [
        {"sensor_type": "headbox_stock_consistency",  "component_id": "headbox",  "unit": "%",    "value": 0.32,  "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "headbox_jet_velocity",       "component_id": "headbox",  "unit": "m/s",  "value": 25.4,  "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "visconip_nip_load",          "component_id": "visconip", "unit": "kN/m", "value": 95,    "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "visconip_felt_moisture",     "component_id": "visconip", "unit": "%",    "value": 41.2,  "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "yankee_surface_temp",        "component_id": "yankee",   "unit": "°C",   "value": 112.4, "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "yankee_steam_pressure",      "component_id": "yankee",   "unit": "bar",  "value": 9.6,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "yankee_vibration_bearing_3", "component_id": "yankee",   "unit": "mm/s", "value": 3.1,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "aircap_inlet_temp",          "component_id": "aircap",   "unit": "°C",   "value": 478,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "aircap_exhaust_humidity",    "component_id": "aircap",   "unit": "%",    "value": 38,    "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "softreel_tension",           "component_id": "softreel", "unit": "N/m",  "value": 198,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "softreel_drive_current",     "component_id": "softreel", "unit": "A",    "value": 142,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "rewinder_drive_current",     "component_id": "rewinder", "unit": "A",    "value": 88,    "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "rewinder_dancer_position",   "component_id": "rewinder", "unit": "mm",   "value": 24,    "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
        {"sensor_type": "qcs_basis_weight_cd_stddev", "component_id": "rewinder", "unit": "g/m²", "value": 0.8,   "is_anomaly": False, "timestamp": _RUNNING_SENSOR_TIMESTAMP},
    ],
}


def get_components(machine_id: str) -> dict:
    _machine_or_raise(machine_id)
    rows_by_id = {r["component_id"]: r for r in _COMPONENTS_BY_MACHINE[machine_id]}
    components = []
    for meta in COMPONENTS_IN_ORDER:
        cid = meta["component_id"]
        row = rows_by_id[cid]
        last_maint = row["last_service_date"]
        hours_since = (_ANCHOR_TODAY - date.fromisoformat(last_maint)).days * 24
        components.append({
            "component_id": cid,
            "machine_id": machine_id,
            "name": meta["name"],
            "is_critical": meta["is_critical"],
            "risk_score": 100 - int(row["health_score"]),
            "risk_tier": row["tier"],
            "expected_lifetime_hours": meta["expected_lifetime_hours"],
            "hours_since_last_maintenance": hours_since,
            "last_maintenance_date": last_maint,
        })
    return {"machine_id": machine_id, "components": components}


def get_sensors(machine_id: str) -> dict:
    _machine_or_raise(machine_id)
    readings = [
        {
            "sensor_type": r["sensor_type"],
            "machine_id": machine_id,
            "component_id": r["component_id"],
            "value": r["value"],
            "unit": r["unit"],
            "timestamp": r["timestamp"],
            "is_anomaly": r["is_anomaly"],
        }
        for r in _SENSORS_BY_MACHINE[machine_id]
    ]
    return {"machine_id": machine_id, "readings": readings, "last_updated": _now_iso()}


# ---------------------------------------------------------------------------
# Alarms — Valmet DNA DCS event log. Generation logic is a Python port of
# frontend/app/src/mockData.js > genAlarms (verbatim message catalog +
# ordering math), so the API output stays in lockstep with the frontend's
# placeholder alarms while the parquet ETL doesn't yet exist.
# ---------------------------------------------------------------------------

# Anchor "now" — same constant as JS `new Date('2026-04-28T09:30:00Z')`.
_ALARMS_BASE_TIME = datetime(2026, 4, 28, 9, 30, tzinfo=timezone.utc)

# 18-row template catalog. Order and content match mockData.js verbatim;
# rotation index `(i + seed) % 18` selects which template a given alarm
# uses, so the per-machine seeds yield distinct-but-overlapping sequences.
_ALARM_TEMPLATES: list[dict] = [
    {"severity": "critical", "message": "Bearing 3 vibration trending above warning limit",  "component_id": "yankee"},
    {"severity": "warning",  "message": "PV-2102 deviation > 5%",                              "component_id": "yankee"},
    {"severity": "warning",  "message": "Yankee steam header pressure oscillation",            "component_id": "yankee"},
    {"severity": "warning",  "message": "Bearing 3 temperature trending above warning limit",  "component_id": "yankee"},
    {"severity": "info",     "message": "Yankee surface temp deviation < 2°C",                 "component_id": "yankee"},
    {"severity": "warning",  "message": "ViscoNip felt moisture above target",                 "component_id": "visconip"},
    {"severity": "warning",  "message": "Nip load fluctuation outside band",                   "component_id": "visconip"},
    {"severity": "info",     "message": "Felt life advisory — 22% remaining",                  "component_id": "visconip"},
    {"severity": "warning",  "message": "Hood damper position fault",                          "component_id": "aircap"},
    {"severity": "warning",  "message": "AirCap inlet temp setpoint deviation",                "component_id": "aircap"},
    {"severity": "info",     "message": "Exhaust humidity drift — burner re-tune advised",     "component_id": "aircap"},
    {"severity": "warning",  "message": "Stock consistency setpoint deviation",                "component_id": "headbox"},
    {"severity": "info",     "message": "Headbox jet velocity deviation < 1%",                 "component_id": "headbox"},
    {"severity": "warning",  "message": "QCS scanner CD profile out of band",                  "component_id": "rewinder"},
    {"severity": "warning",  "message": "Reel build-up rate fault",                            "component_id": "softreel"},
    {"severity": "warning",  "message": "Dancer position out of tolerance",                    "component_id": "rewinder"},
    {"severity": "info",     "message": "Drive current spike — single event",                  "component_id": "rewinder"},
    {"severity": "info",     "message": "SoftReel tension trending low",                       "component_id": "softreel"},
]


def _format_iso_z(dt: datetime) -> str:
    """Contract canonical ISO format — no milliseconds, Z suffix."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _alarm_downtime_minutes(severity: str, resolved: bool, i: int) -> int:
    """Deterministic downtime per alarm. 0 for unresolved alarms (still
    in flight) and for info-severity advisories. Resolved warning/critical
    alarms map to bounded ranges keyed off the loop index ``i`` so the
    output is reproducible across runs."""
    if not resolved or severity == "info":
        return 0
    if severity == "warning":
        return (i % 11) + 5     # 5..15 inclusive
    if severity == "critical":
        return (i % 31) + 15    # 15..45 inclusive
    return 0


def _gen_alarms(machine_id: str, count: int, seed: int) -> list[dict]:
    """Python port of mockData.js > genAlarms. Output is contract-shaped:
    {alarm_id, timestamp, severity, description, resolved_at, downtime
    _minutes}. machine_id, component_id and the raw resolved flag from
    mockData are intentionally dropped (machine_id is on the wrapper;
    component_id and resolved aren't on the contract's per-alarm shape).
    """
    out: list[dict] = []
    for i in range(count):
        tmpl = _ALARM_TEMPLATES[(i + seed) % len(_ALARM_TEMPLATES)]
        minutes_ago = i * 47 + (i * i) % 23 + 5
        raised = _ALARMS_BASE_TIME - timedelta(minutes=minutes_ago)
        # First 5 alarms (i ≤ 4) always unresolved — they're "in flight".
        resolved = (i > 4) and ((i * 7 + seed) % 3 != 0)
        timestamp = _format_iso_z(raised)
        resolved_at = _format_iso_z(raised + timedelta(minutes=30)) if resolved else None
        out.append({
            "alarm_id": f"alm-{machine_id}-{(count - i):04d}",
            "timestamp": timestamp,
            "severity": tmpl["severity"],
            "description": tmpl["message"],
            "resolved_at": resolved_at,
            "downtime_minutes": _alarm_downtime_minutes(tmpl["severity"], resolved, i),
        })
    return out


# Per-machine (count, seed) pairs — same numbers as mockData.js so the
# precomputed alarm streams are byte-identical in content / ordering.
_ALARM_COUNTS_AND_SEEDS: dict[str, tuple[int, int]] = {
    "al-nakheel": (34, 0),
    "al-bardi":   (31, 3),
    "al-sindian": (30, 7),
    "al-snobar":  (30, 11),
}

_ALARMS_BY_MACHINE: dict[str, list[dict]] = {
    mid: _gen_alarms(mid, count, seed)
    for mid, (count, seed) in _ALARM_COUNTS_AND_SEEDS.items()
}


def get_alarms(
    machine_id: str,
    limit: int = 50,
    severity: Optional[str] = None,
) -> dict:
    _machine_or_raise(machine_id)
    items = list(_ALARMS_BY_MACHINE[machine_id])
    if severity is not None:
        items = [a for a in items if a["severity"] == severity]
    # Sort newest-first BEFORE limit so a small ?limit= still shows the
    # most recent alarms — what the frontend's ticker needs.
    items.sort(key=lambda a: a["timestamp"], reverse=True)
    items = items[:limit]
    return {
        "machine_id": machine_id,
        "alarms": [dict(a) for a in items],
        "total": len(items),
    }


# ---------------------------------------------------------------------------
# Maintenance log — verbatim mirror of frontend mockData.js >
# maintenanceLogByMachine. Translated to contract field names at response
# time (entry_id → log_id, kind → maintenance_type, summary → notes, etc.)
# so the source data stays in lockstep with the frontend.
# ---------------------------------------------------------------------------

# 'inspection' isn't in the contract enum {preventive, corrective,
# predictive, emergency}; map it to the closest semantic neighbour.
_MAINTENANCE_TYPE_MAP: dict[str, str] = {
    "preventive": "preventive",
    "corrective": "corrective",
    "inspection": "preventive",
}

_MAINTENANCE_BY_MACHINE: dict[str, list[dict]] = {
    "al-nakheel": [
        {"entry_id": "mnt-aln-0008", "date": "2026-03-05", "kind": "preventive", "component_id": "rewinder", "summary": "Replaced rewinder drive belt and tensioner.",                                "cost_usd":  4800, "technician": "A. Khalil"},
        {"entry_id": "mnt-aln-0007", "date": "2026-02-14", "kind": "preventive", "component_id": "headbox",  "summary": "Cleaned and inspected headbox slice. No anomalies.",                          "cost_usd":  2200, "technician": "M. Said"},
        {"entry_id": "mnt-aln-0006", "date": "2026-01-20", "kind": "preventive", "component_id": "softreel", "summary": "Replaced creping blade. Set angle to 18°.",                                   "cost_usd":  6400, "technician": "A. Khalil"},
        {"entry_id": "mnt-aln-0005", "date": "2025-12-02", "kind": "inspection", "component_id": "aircap",   "summary": "Infrared scan of hood + burner tuning. Note: bearing 3 watchlist.",           "cost_usd":  1800, "technician": "External (Valmet)"},
        {"entry_id": "mnt-aln-0004", "date": "2025-11-08", "kind": "preventive", "component_id": "visconip", "summary": "Felt change. Old felt at 11% life remaining.",                                "cost_usd": 28500, "technician": "A. Khalil"},
        {"entry_id": "mnt-aln-0003", "date": "2025-10-12", "kind": "inspection", "component_id": "yankee",   "summary": "Vibration analysis on Yankee bearings. Bearing 3 baseline 2.4 mm/s.",         "cost_usd":  2400, "technician": "External (Valmet)"},
        {"entry_id": "mnt-aln-0002", "date": "2024-09-12", "kind": "corrective", "component_id": "yankee",   "summary": "Replaced bearings 1 and 2. Bearing 3 left in service per OEM.",               "cost_usd": 11200, "technician": "External (Valmet)"},
        {"entry_id": "mnt-aln-0001", "date": "2024-08-04", "kind": "preventive", "component_id": "rewinder", "summary": "Quarterly drive inspection. Lubrication topped up.",                          "cost_usd":  1500, "technician": "M. Said"},
    ],
    "al-bardi": [
        {"entry_id": "mnt-alb-0009", "date": "2026-03-01", "kind": "preventive", "component_id": "headbox",  "summary": "Headbox flush + slice inspection.",                                           "cost_usd":  2400, "technician": "H. Farouk"},
        {"entry_id": "mnt-alb-0008", "date": "2026-02-18", "kind": "preventive", "component_id": "rewinder", "summary": "Belt and bearing inspection on main drive.",                                  "cost_usd":  1600, "technician": "H. Farouk"},
        {"entry_id": "mnt-alb-0007", "date": "2025-12-10", "kind": "inspection", "component_id": "aircap",   "summary": "Annual hood inspection. Damper actuators within spec.",                       "cost_usd":  1900, "technician": "External (Valmet)"},
        {"entry_id": "mnt-alb-0006", "date": "2025-11-28", "kind": "corrective", "component_id": "softreel", "summary": "Dancer load cell recalibration after drift fault.",                           "cost_usd":  3200, "technician": "H. Farouk"},
        {"entry_id": "mnt-alb-0005", "date": "2025-10-22", "kind": "preventive", "component_id": "visconip", "summary": "Felt change. New felt installed and tensioned.",                              "cost_usd": 26800, "technician": "External (Valmet)"},
        {"entry_id": "mnt-alb-0004", "date": "2025-09-30", "kind": "corrective", "component_id": "yankee",   "summary": "PRV stiction repair on steam header.",                                        "cost_usd":  5400, "technician": "External (Valmet)"},
        {"entry_id": "mnt-alb-0003", "date": "2025-08-15", "kind": "corrective", "component_id": "yankee",   "summary": "Replaced bearing 1 after vibration trend exceeded threshold.",                "cost_usd": 12400, "technician": "External (Valmet)"},
        {"entry_id": "mnt-alb-0002", "date": "2025-07-04", "kind": "preventive", "component_id": "softreel", "summary": "Creping blade replacement.",                                                   "cost_usd":  5800, "technician": "H. Farouk"},
        {"entry_id": "mnt-alb-0001", "date": "2025-06-12", "kind": "inspection", "component_id": "rewinder", "summary": "Quarterly inspection. No findings.",                                           "cost_usd":  1400, "technician": "H. Farouk"},
    ],
    "al-sindian": [
        {"entry_id": "mnt-als-0010", "date": "2026-04-22", "kind": "corrective", "component_id": "rewinder", "summary": "IN PROGRESS — drive current spike investigation. Vibration analysis underway.", "cost_usd":     0, "technician": "External (Valmet)"},
        {"entry_id": "mnt-als-0009", "date": "2026-04-22", "kind": "preventive", "component_id": "visconip", "summary": "IN PROGRESS — scheduled felt change.",                                           "cost_usd":     0, "technician": "O. Mansour"},
        {"entry_id": "mnt-als-0008", "date": "2026-02-20", "kind": "preventive", "component_id": "aircap",   "summary": "Burner tuning + damper inspection.",                                            "cost_usd":  2700, "technician": "O. Mansour"},
        {"entry_id": "mnt-als-0007", "date": "2026-01-10", "kind": "preventive", "component_id": "headbox",  "summary": "Headbox cleaning and gasket replacement.",                                      "cost_usd":  3100, "technician": "O. Mansour"},
        {"entry_id": "mnt-als-0006", "date": "2025-12-15", "kind": "preventive", "component_id": "visconip", "summary": "Nip load calibration.",                                                         "cost_usd":  1900, "technician": "O. Mansour"},
        {"entry_id": "mnt-als-0005", "date": "2025-11-04", "kind": "preventive", "component_id": "yankee",   "summary": "Steam trap inspection and replacement.",                                        "cost_usd":  4200, "technician": "External (Valmet)"},
        {"entry_id": "mnt-als-0004", "date": "2025-10-30", "kind": "inspection", "component_id": "softreel", "summary": "Drive bearing thermography scan.",                                              "cost_usd":  1600, "technician": "External (Valmet)"},
        {"entry_id": "mnt-als-0003", "date": "2025-09-18", "kind": "corrective", "component_id": "rewinder", "summary": "Dancer position sensor replacement.",                                           "cost_usd":  3400, "technician": "O. Mansour"},
        {"entry_id": "mnt-als-0002", "date": "2025-08-01", "kind": "preventive", "component_id": "softreel", "summary": "Creping blade replacement.",                                                    "cost_usd":  5200, "technician": "O. Mansour"},
        {"entry_id": "mnt-als-0001", "date": "2025-06-22", "kind": "inspection", "component_id": "yankee",   "summary": "Annual Yankee bearing inspection.",                                             "cost_usd":  2800, "technician": "External (Valmet)"},
    ],
    "al-snobar": [
        {"entry_id": "mnt-asn-0008", "date": "2026-03-22", "kind": "preventive", "component_id": "headbox",  "summary": "Headbox slice cleaning.",                                                      "cost_usd":  1900, "technician": "R. Haddad"},
        {"entry_id": "mnt-asn-0007", "date": "2026-03-10", "kind": "preventive", "component_id": "rewinder", "summary": "Drive inspection. Lubrication topped up.",                                     "cost_usd":  1300, "technician": "R. Haddad"},
        {"entry_id": "mnt-asn-0006", "date": "2026-02-08", "kind": "preventive", "component_id": "aircap",   "summary": "Burner re-tune and damper actuator check.",                                    "cost_usd":  2500, "technician": "R. Haddad"},
        {"entry_id": "mnt-asn-0005", "date": "2026-01-15", "kind": "preventive", "component_id": "softreel", "summary": "Creping blade replacement and angle calibration.",                              "cost_usd":  5600, "technician": "R. Haddad"},
        {"entry_id": "mnt-asn-0004", "date": "2026-01-05", "kind": "preventive", "component_id": "visconip", "summary": "Felt inspection. Life remaining 38% — schedule swap.",                          "cost_usd":  1200, "technician": "R. Haddad"},
        {"entry_id": "mnt-asn-0003", "date": "2025-11-30", "kind": "inspection", "component_id": "yankee",   "summary": "Vibration baseline scan. All bearings within spec.",                            "cost_usd":  2100, "technician": "External (Valmet)"},
        {"entry_id": "mnt-asn-0002", "date": "2025-10-18", "kind": "preventive", "component_id": "rewinder", "summary": "Dancer recalibration after seasonal humidity shift.",                            "cost_usd":  1800, "technician": "R. Haddad"},
        {"entry_id": "mnt-asn-0001", "date": "2025-09-04", "kind": "preventive", "component_id": "headbox",  "summary": "Stock consistency loop tuning.",                                                "cost_usd":  1400, "technician": "R. Haddad"},
    ],
}


def _maint_downtime_hours(cost_usd: float) -> int:
    """Deterministic estimate from cost. Rough technician rate ~$1750/hr,
    clamped to [1, 12] for non-zero cost. In-progress work (cost=0) shows
    0 hours since the actual outage time hasn't been booked yet."""
    if not cost_usd:
        return 0
    return max(1, min(12, round(cost_usd / 1750)))


def _translate_maint_entry(entry: dict) -> dict:
    """Apply the mockData → contract field renames + maintenance_type map
    + downtime_hours computation. Output keys exactly match the contract's
    Maintenance log object shape."""
    return {
        "log_id": entry["entry_id"],
        "component_id": entry["component_id"],
        "maintenance_type": _MAINTENANCE_TYPE_MAP[entry["kind"]],
        "date_performed": entry["date"],
        "cost_usd": entry["cost_usd"],
        "downtime_hours": _maint_downtime_hours(entry["cost_usd"]),
        "technician": entry["technician"],
        "notes": entry["summary"],
    }


def get_maintenance_log(machine_id: str) -> dict:
    _machine_or_raise(machine_id)
    return {
        "machine_id": machine_id,
        "logs": [_translate_maint_entry(e) for e in _MAINTENANCE_BY_MACHINE[machine_id]],
    }


# ---------------------------------------------------------------------------
# Sensor history — Python port of frontend/app/src/mockData.js > genHistory.
# Same trig-driven curve so the API output stays in lockstep with the
# frontend's chart renderer until parquet ETL takes over. Anchor "now" is
# reused from the alarms section (one shared canonical timestamp keeps the
# UI's various time-axes aligned).
# ---------------------------------------------------------------------------

# Normal operating range per sensor_type — physical property of the sensor,
# machine-independent. Keys mirror sensorsByMachine in mockData.js.
_SENSOR_NORMAL_RANGES: dict[str, tuple[float, float]] = {
    "headbox_stock_consistency":  (0.28, 0.34),
    "headbox_jet_velocity":       (23.0, 27.0),
    "visconip_nip_load":          (85.0, 110.0),
    "visconip_felt_moisture":     (35.0, 45.0),
    "yankee_surface_temp":        (108.0, 118.0),
    "yankee_steam_pressure":      (9.0, 10.5),
    "yankee_vibration_bearing_3": (2.0, 4.0),
    "aircap_inlet_temp":          (470.0, 490.0),
    "aircap_exhaust_humidity":    (32.0, 42.0),
    "softreel_tension":           (180.0, 220.0),
    "softreel_drive_current":     (130.0, 160.0),
    "rewinder_drive_current":     (75.0, 105.0),
    "rewinder_dancer_position":   (18.0, 32.0),
    "qcs_basis_weight_cd_stddev": (0.4, 1.2),
}

# Cap raw (minute-level) point count so a 30d ?aggregation=raw query stays
# bounded. 1440 = the most recent 24 hours at minute resolution, which is
# what the chart actually renders usefully anyway.
_RAW_POINTS_CAP = 1440


def _resolve_history_grid(window: str, aggregation: str) -> tuple[int, int]:
    """Return (n_points, step_seconds) for a given window/aggregation. The
    upstream FastAPI route enforces the enum so we can KeyError here on a
    bad value — it should never reach this layer in practice."""
    window_minutes = {"1h": 60, "24h": 1440, "7d": 7 * 1440, "30d": 30 * 1440}[window]
    if aggregation == "hourly":
        # 1 point per hour, minimum 1 (so 1h = 1 point not 0).
        return max(1, window_minutes // 60), 3600
    if aggregation == "daily":
        # 1 point per day, minimum 1 (so 1h/24h both yield 1 daily point).
        return max(1, window_minutes // 1440), 86400
    if aggregation == "raw":
        return min(window_minutes, _RAW_POINTS_CAP), 60
    raise KeyError(f"unknown aggregation {aggregation!r}")


def _gen_sensor_history_points(
    value: float,
    normal_range: tuple[float, float],
    is_anomaly: bool,
    n_points: int,
    step_seconds: int,
) -> list[dict]:
    """Port of mockData.js > genHistory generalised over (n_points, step).
    The trig multipliers (0.7, 1.3, 0.4) and exponent (1.6) are taken
    from the JS verbatim and applied to the loop index ``i`` so the curve
    is deterministic and reproducible across runs.

    The contract requires per-point ``min`` and ``max`` for chart band
    rendering. These are NOT real time-bucket aggregates — they're a
    synthetic ±5%-of-range band around ``value`` that gives the line
    chart a visible confidence ribbon. When parquet ETL lands, this
    function is the one swap point that needs upgrading to real bucket
    min/max.
    """
    lo, hi = normal_range
    range_width = hi - lo
    band = round(0.05 * range_width, 4)

    # Maintenance / no-reading short-circuit. al-sindian's underlying
    # sensor rows have value=0 with the maint timestamp; the chart should
    # render a flat zero line, not a noise-driven oscillation around 0.
    if value == 0:
        anchor_zeroes: list[dict] = []
        for i in range(n_points - 1, -1, -1):
            t = _ALARMS_BASE_TIME - timedelta(seconds=i * step_seconds)
            anchor_zeroes.append({
                "timestamp": _format_iso_z(t),
                "value": 0,
                "min": 0,
                "max": 0,
            })
        return anchor_zeroes

    mid = (lo + hi) / 2.0
    start = mid if is_anomaly else value

    points: list[dict] = []
    for i in range(n_points - 1, -1, -1):
        # A lone point (n_points == 1) sits at "now" and represents the
        # current state, so progress = 1.0 — without this short-circuit
        # the JS-style formula divides by zero AND would place the point
        # at the oldest end of the curve.
        if n_points == 1:
            progress = 1.0
        else:
            progress = (n_points - 1 - i) / (n_points - 1)
        noise = (math.sin(0.7 * i) + math.cos(1.3 * i)) * range_width * 0.04
        if is_anomaly:
            v = start + (value - start) * (progress ** 1.6) + noise
        else:
            v = value + noise + math.sin(0.4 * i) * range_width * 0.05
        v = round(v, 2)
        t = _ALARMS_BASE_TIME - timedelta(seconds=i * step_seconds)
        points.append({
            "timestamp": _format_iso_z(t),
            "value": v,
            "min": round(v - band, 2),
            "max": round(v + band, 2),
        })
    return points


def _sensor_row(machine_id: str, sensor_type: str) -> dict:
    """Look up the current sensor reading row from _SENSORS_BY_MACHINE.
    Raises SensorNotFound if the sensor_type isn't present for the given
    machine. Caller is responsible for the prior MachineNotFound check."""
    for r in _SENSORS_BY_MACHINE[machine_id]:
        if r["sensor_type"] == sensor_type:
            return r
    raise SensorNotFound(machine_id, sensor_type)


def get_sensor_history(
    machine_id: str,
    sensor_type: str,
    window: str = "24h",
    aggregation: str = "hourly",
) -> dict:
    _machine_or_raise(machine_id)
    row = _sensor_row(machine_id, sensor_type)
    normal_range = _SENSOR_NORMAL_RANGES[sensor_type]
    n_points, step_seconds = _resolve_history_grid(window, aggregation)
    points = _gen_sensor_history_points(
        value=row["value"],
        normal_range=normal_range,
        is_anomaly=row["is_anomaly"],
        n_points=n_points,
        step_seconds=step_seconds,
    )
    lo, hi = normal_range
    return {
        "machine_id": machine_id,
        "sensor_type": sensor_type,
        "unit": row["unit"],
        "window": window,
        "aggregation": aggregation,
        "normal_range": {"min": lo, "max": hi},
        "points": points,
    }


# ---------------------------------------------------------------------------
# Cost savings — ROI tracker. The ytd baseline matches the contract's
# example response verbatim; other windows scale proportionally so the
# four windows feel like a coherent narrative on the dashboard.
# ---------------------------------------------------------------------------

_COST_SAVINGS_YTD_BASELINE = {
    "total_predictions": 23,
    "predictions_acted_on": 18,
    "estimated_downtime_hours_prevented": 47,
    "estimated_cost_saved_usd": 940_000,
    "breakdown": {
        "al-nakheel": 480_000,
        "al-bardi":   220_000,
        "al-sindian": 160_000,
        "al-snobar":   80_000,
    },
}

# Scale factors relative to ytd. mtd is "month-to-date" (~6 weeks of the
# year), qtd is "quarter-to-date" (~3.5 months), all extends ytd into a
# trailing-12-months total.
_COST_SAVINGS_WINDOW_SCALE = {
    "mtd": 0.15,
    "qtd": 0.40,
    "ytd": 1.00,
    "all": 1.60,
}


def _round_to_thousand(usd: float) -> int:
    return int(round(usd / 1000.0) * 1000)


def get_cost_savings(window: str) -> dict:
    """Return the contract-shaped /kpis/cost-savings payload for the given
    window. The breakdown_by_machine entries always sum exactly to
    estimated_cost_saved_usd — any rounding drift is absorbed by the
    largest machine's entry (al-nakheel, the most-saved-on)."""
    if window not in _COST_SAVINGS_WINDOW_SCALE:
        raise ValueError(f"unknown window {window!r}")

    scale = _COST_SAVINGS_WINDOW_SCALE[window]
    base = _COST_SAVINGS_YTD_BASELINE

    total_predictions = int(round(base["total_predictions"] * scale))
    predictions_acted_on = int(round(base["predictions_acted_on"] * scale))
    downtime_hours = int(round(base["estimated_downtime_hours_prevented"] * scale))
    total_cost_saved = _round_to_thousand(base["estimated_cost_saved_usd"] * scale)

    # Scale + round each machine's contribution, then absorb any drift
    # in the largest entry so the breakdown sums exactly to the total.
    breakdown_unsorted = [
        {"machine_id": mid, "cost_saved_usd": _round_to_thousand(amt * scale)}
        for mid, amt in base["breakdown"].items()
    ]
    drift = total_cost_saved - sum(b["cost_saved_usd"] for b in breakdown_unsorted)
    if drift != 0:
        # Largest entry by current cost takes the correction.
        largest = max(breakdown_unsorted, key=lambda b: b["cost_saved_usd"])
        largest["cost_saved_usd"] += drift

    return {
        "window": window,
        "total_predictions": total_predictions,
        "predictions_acted_on": predictions_acted_on,
        "estimated_downtime_hours_prevented": downtime_hours,
        "estimated_cost_saved_usd": total_cost_saved,
        "breakdown_by_machine": breakdown_unsorted,
    }


# ---------------------------------------------------------------------------
# Demand catalog — products + markets. Static seed files kept under
# ``backend/data/`` so they can be edited without touching code, and so
# the parquet ETL can read the same SKU list.
# ---------------------------------------------------------------------------

_DEMAND_SEED_DIR = Path(__file__).parent / "data"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


_PRODUCTS_DOC = _load_json(_DEMAND_SEED_DIR / "products.json")
_MARKETS_DOC = _load_json(_DEMAND_SEED_DIR / "markets.json")

# Index for O(1) lookup; the .json keeps definition order so ``products``
# in the response stays in catalog order.
_PRODUCTS_BY_SKU: dict[str, dict] = {p["sku"]: p for p in _PRODUCTS_DOC["products"]}
_MARKETS_BY_ID: dict[str, dict] = {m["market_id"]: m for m in _MARKETS_DOC["markets"]}


class ProductNotFound(KeyError):
    def __init__(self, sku: str):
        super().__init__(sku)
        self.sku = sku


class MarketNotFound(KeyError):
    def __init__(self, market_id: str):
        super().__init__(market_id)
        self.market_id = market_id


def get_products() -> dict:
    products = list(_PRODUCTS_DOC["products"])
    return {"products": products, "total": len(products)}


def get_markets() -> dict:
    return {"markets": list(_MARKETS_DOC["markets"])}


def _product_or_raise(sku: str) -> dict:
    if sku not in _PRODUCTS_BY_SKU:
        raise ProductNotFound(sku)
    return _PRODUCTS_BY_SKU[sku]


def _market_or_raise(market_id: str) -> dict:
    if market_id not in _MARKETS_BY_ID:
        raise MarketNotFound(market_id)
    return _MARKETS_BY_ID[market_id]


# ---------------------------------------------------------------------------
# Demand history (parquet) + anomalies + seasonality.
# ---------------------------------------------------------------------------

_DEMAND_HISTORY_PATH = _DEMAND_SEED_DIR / "demand_history.parquet"


def _try_load_demand_history() -> Optional[pd.DataFrame]:
    if not _DEMAND_HISTORY_PATH.exists():
        return None
    try:
        df = pd.read_parquet(_DEMAND_HISTORY_PATH)
        df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception:
        return None


_DEMAND_HISTORY: Optional[pd.DataFrame] = _try_load_demand_history()


def demand_history_loaded() -> bool:
    return _DEMAND_HISTORY is not None


def get_demand_history(sku: str, market: str) -> pd.DataFrame:
    """Return the (date, units_sold) history for a (sku, market) pair, sorted
    ascending. Raises ProductNotFound / MarketNotFound for unknown IDs."""
    _product_or_raise(sku)
    _market_or_raise(market)
    if _DEMAND_HISTORY is None:
        raise FileNotFoundError(
            f"demand_history.parquet not found at {_DEMAND_HISTORY_PATH}. "
            f"Run `python backend/data/generate_demand_history.py` first."
        )
    df = _DEMAND_HISTORY[
        (_DEMAND_HISTORY["sku"] == sku) & (_DEMAND_HISTORY["market"] == market)
    ].copy()
    return df.sort_values("date").reset_index(drop=True)


# Seasonality events block — contract values, fleet-wide. Per-SKU
# yearly_pattern is computed from the history below.
_SEASONALITY_EVENTS: list[dict] = [
    {"name": "ramadan",        "average_lift_percent": 35},
    {"name": "eid_al_fitr",    "average_lift_percent": 22},
    {"name": "back_to_school", "average_lift_percent": 12},
]


def get_seasonality(sku: str, market: Optional[str] = None) -> dict:
    _product_or_raise(sku)
    if market is not None:
        _market_or_raise(market)
    if _DEMAND_HISTORY is None:
        raise FileNotFoundError(
            f"demand_history.parquet not found at {_DEMAND_HISTORY_PATH}."
        )

    df = _DEMAND_HISTORY[_DEMAND_HISTORY["sku"] == sku]
    if market is not None:
        df = df[df["market"] == market]
    if df.empty:
        # Should be unreachable since we validated sku + market above.
        raise ProductNotFound(sku)

    monthly_avg = df.groupby(df["date"].dt.month)["units_sold"].mean()
    overall_avg = float(df["units_sold"].mean())
    yearly_pattern = [
        {"month": int(m), "index": round(float(monthly_avg.get(m, overall_avg) / overall_avg), 2)}
        for m in range(1, 13)
    ]
    return {
        "sku": sku,
        "market": market,
        "yearly_pattern": yearly_pattern,
        "events": [dict(e) for e in _SEASONALITY_EVENTS],
    }


# Three deliberate anomalies seeded into demand_history.parquet — these
# are the exact rows /demand/anomalies returns. ``detected_at`` is set
# in April 2026 so the page feels current.
_DEMAND_ANOMALIES: list[dict] = [
    {
        "anomaly_id": "anm-2026-04-22-001",
        "sku": "fine-baby-s3",
        "market": "ksa",
        "detected_at": "2026-04-22",
        "type": "spike",
        "magnitude_percent": 47,
        "explanation": "Sales 47% above expected — possible distributor restocking or demand surge.",
    },
    {
        "anomaly_id": "anm-2026-04-15-002",
        "sku": "fine-toilet-3ply",
        "market": "uae",
        "detected_at": "2026-04-15",
        "type": "dip",
        "magnitude_percent": 32,
        "explanation": "Sales 32% below expected — short-term supply disruption flagged in operations log.",
    },
    {
        "anomaly_id": "anm-2026-04-08-003",
        "sku": "fine-facial-200",
        "market": "egypt",
        "detected_at": "2026-04-08",
        "type": "trend_break",
        "magnitude_percent": 18,
        "explanation": "Sustained 18% downward shift since April 2025. Possible competitor entry or category re-pricing.",
    },
]


def get_demand_anomalies() -> dict:
    return {"anomalies": [dict(a) for a in _DEMAND_ANOMALIES]}


# ---------------------------------------------------------------------------
# Forecast (Prophet). Models are fit lazily on first call per (sku, market)
# and cached in-process — re-fitting takes ~1-3s per pair so repeat calls
# from the dashboard return instantly.
# ---------------------------------------------------------------------------

# Anchor "today" for the demo: forecasts always start at the first day of
# the next month from this anchor. Locked so the forecast window is
# reproducible across runs even when the wall clock advances.
_FORECAST_ANCHOR_DATE = date(2026, 4, 25)
_FORECAST_HORIZON_MIN = 1
_FORECAST_HORIZON_MAX = 12

# Holiday dates fed into Prophet so the model picks up Ramadan/Eid lifts
# in the historical signal. ``upper_window`` covers the duration of the
# event (Ramadan ≈ 30 days, Eid ≈ 3 days).
_PROPHET_HOLIDAYS = pd.DataFrame({
    "holiday": [
        "ramadan", "ramadan", "ramadan",
        "eid_al_fitr", "eid_al_fitr", "eid_al_fitr",
    ],
    "ds": pd.to_datetime([
        "2024-03-10", "2025-03-01", "2026-02-18",
        "2024-04-10", "2025-03-30", "2026-03-20",
    ]),
    "lower_window": [0, 0, 0, 0, 0, 0],
    "upper_window": [29, 29, 29, 3, 3, 3],
})

# Seasonality event markers returned in the /forecast response. These are
# the contract's stylized values — anchor-relative, illustrative, suitable
# for the chart's "Ramadan / Eid begins" reference lines.
_FORECAST_SEASONALITY_EVENTS: list[dict] = [
    {"date": "2026-03-10", "label": "Ramadan begins", "expected_lift_percent": 35},
    {"date": "2026-04-09", "label": "Eid al-Fitr",    "expected_lift_percent": 22},
]

_FORECAST_REGRESSORS = ["historical_sales", "ramadan_calendar", "b2b_pipeline"]

# Cache of fitted Prophet models keyed by (sku, market). Cleared by
# reset_forecast_cache() if needed (for tests).
_FORECAST_MODEL_CACHE: dict[tuple[str, str], "object"] = {}


def reset_forecast_cache() -> None:
    _FORECAST_MODEL_CACHE.clear()


def _next_month_start(d: date) -> pd.Timestamp:
    """First day of the month after ``d``. 2026-04-25 -> 2026-05-01."""
    if d.month == 12:
        return pd.Timestamp(year=d.year + 1, month=1, day=1)
    return pd.Timestamp(year=d.year, month=d.month + 1, day=1)


def _fit_prophet_model(sku: str, market: str):
    """Fit a Prophet model on the (sku, market) history and return it.
    Importing inside the function keeps module-import time low for
    callers that never hit /forecast (Module 1 endpoints, etc.)."""
    from prophet import Prophet  # noqa: WPS433 — local import is intentional.

    history = get_demand_history(sku, market)
    df = history[["date", "units_sold"]].rename(columns={"date": "ds", "units_sold": "y"})

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        holidays=_PROPHET_HOLIDAYS,
        interval_width=0.85,
    )
    model.fit(df)
    return model


def _get_or_fit_forecast_model(sku: str, market: str):
    key = (sku, market)
    if key not in _FORECAST_MODEL_CACHE:
        _FORECAST_MODEL_CACHE[key] = _fit_prophet_model(sku, market)
    return _FORECAST_MODEL_CACHE[key]


def get_forecast(sku: str, market: str, horizon_months: int) -> dict:
    """Return the contract-shaped /forecast payload for (sku, market). Fits
    a Prophet model on the seeded demand history (with Ramadan + Eid as
    holidays) and predicts ``horizon_months`` months starting from the
    first of the month after the demo anchor (2026-05-01 onward)."""
    if not (_FORECAST_HORIZON_MIN <= horizon_months <= _FORECAST_HORIZON_MAX):
        raise ValueError(
            f"horizon_months {horizon_months} outside [{_FORECAST_HORIZON_MIN}, "
            f"{_FORECAST_HORIZON_MAX}]"
        )

    _product_or_raise(sku)
    _market_or_raise(market)

    model = _get_or_fit_forecast_model(sku, market)

    start = _next_month_start(_FORECAST_ANCHOR_DATE)
    future_dates = pd.date_range(start=start, periods=horizon_months, freq="MS")
    future_df = pd.DataFrame({"ds": future_dates})
    pred = model.predict(future_df)

    forecast_points: list[dict] = []
    for _, row in pred.iterrows():
        forecast_points.append({
            "date": row["ds"].strftime("%Y-%m-%d"),
            "forecast_value": int(round(float(row["yhat"]))),
            "lower_bound":    int(round(float(row["yhat_lower"]))),
            "upper_bound":    int(round(float(row["yhat_upper"]))),
        })

    return {
        "sku": sku,
        "market": market,
        "horizon_months": horizon_months,
        "model": "prophet",
        "forecast": forecast_points,
        "seasonality_events": [dict(e) for e in _FORECAST_SEASONALITY_EVENTS],
        "regressors_used": list(_FORECAST_REGRESSORS),
        "generated_at": _now_iso(),
    }
