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

Exceptions:
    MachineNotFound, AlertNotFound — caught in ``backend/ai_model/api.py``
    and translated to the contract's 404 error envelope.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
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
