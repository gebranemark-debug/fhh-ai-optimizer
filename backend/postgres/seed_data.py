"""Seed the FHH PostgreSQL relational layer with realistic 6-month demo data.

Reads ``DATABASE_URL`` from the environment (defaults to a local Postgres URL)
and populates every table defined in ``schema.sql``. Re-runnable: drops and
recreates all tables before inserting.

Targets the constants and shapes locked in ``docs/API_CONTRACT-2.md`` v1.1:
- 4 machine IDs, 6 component IDs per machine
- lowercase enums for status, severity, maintenance_type
- ISO timestamps stored as TIMESTAMPTZ in UTC

Run:
    python backend/postgres/seed_data.py
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine, text


# Anchor "today" so the 6 months of demo data align with the API contract's
# example timestamps (April 2026). Reproducible across runs.
TODAY = date(2026, 4, 25)
HISTORY_DAYS = 180

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


# --- Constants pulled verbatim from the API contract ------------------------

MACHINES = [
    {
        "machine_id": "al-nakheel",
        "name": "Al Nakheel",
        "location": "Abu Dhabi, UAE",
        "installation_date": date(2018, 6, 15),
        "status": "running",
        "current_speed_mpm": 2150,
        "current_oee_percent": 94.2,
    },
    {
        "machine_id": "al-bardi",
        "name": "Al Bardi",
        "location": "Egypt",
        "installation_date": date(2015, 9, 1),
        "status": "running",
        "current_speed_mpm": 2080,
        "current_oee_percent": 92.8,
    },
    {
        "machine_id": "al-sindian",
        "name": "Al Sindian",
        "location": "Egypt",
        "installation_date": date(2017, 3, 20),
        "status": "running",
        "current_speed_mpm": 2120,
        "current_oee_percent": 93.5,
    },
    {
        "machine_id": "al-snobar",
        "name": "Al Snobar",
        "location": "Jordan",
        "installation_date": date(2020, 11, 10),
        "status": "running",
        "current_speed_mpm": 2010,
        "current_oee_percent": 91.4,
    },
]

# Component template — IDs and ordering match the API contract exactly.
COMPONENT_TEMPLATE = [
    {"component_id": "headbox",  "name": "OptiFlo II TIS Headbox",        "is_critical": False, "expected_lifetime_hours": 60000},
    {"component_id": "visconip", "name": "Advantage ViscoNip Press",      "is_critical": False, "expected_lifetime_hours": 50000},
    {"component_id": "yankee",   "name": "Cast Alloy Yankee Cylinder",    "is_critical": True,  "expected_lifetime_hours": 50000},
    {"component_id": "aircap",   "name": "AirCap Hood with Air System",   "is_critical": False, "expected_lifetime_hours": 60000},
    {"component_id": "softreel", "name": "SoftReel Reel",                 "is_critical": False, "expected_lifetime_hours": 70000},
    {"component_id": "rewinder", "name": "Focus Rewinder",                "is_critical": False, "expected_lifetime_hours": 70000},
]

PRODUCT_GRADES = ["facial tissue", "toilet paper", "kitchen towel", "napkin"]

SHIFT_DEFS = [
    ("a", time(6, 0)),
    ("b", time(14, 0)),
    ("c", time(22, 0)),
]
SHIFT_HOURS = 8

TECHNICIANS = [
    "M. Khalil", "S. Haddad", "A. Rahman", "Y. Mansour", "N. El-Sayed",
    "R. Khoury", "F. Saleh", "K. Nasser", "L. Aziz", "H. Darwish",
]


# --- Helpers ----------------------------------------------------------------

def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _shift_window(day: date, shift_idx: int) -> tuple[datetime, datetime]:
    """Return (start, end) for a shift on ``day``. Shift C wraps past midnight."""
    _, start_t = SHIFT_DEFS[shift_idx]
    start = _utc(datetime.combine(day, start_t))
    end = start + timedelta(hours=SHIFT_HOURS)
    return start, end


# --- Generators -------------------------------------------------------------

def gen_components() -> list[dict]:
    """One row per (machine, component). 24 rows total. last_maintenance is
    backfilled from maintenance_logs after they're inserted."""
    rows = []
    for m in MACHINES:
        for c in COMPONENT_TEMPLATE:
            rows.append({
                "machine_id": m["machine_id"],
                "component_id": c["component_id"],
                "name": c["name"],
                "is_critical": c["is_critical"],
                "expected_lifetime_hours": c["expected_lifetime_hours"],
                "hours_since_last_maintenance": 0,
                "last_maintenance_date": None,
            })
    return rows


def gen_production_runs(rng: random.Random) -> list[dict]:
    """3 shifts/day x 4 machines x HISTORY_DAYS = ~2,160 rows."""
    rows = []
    start_date = TODAY - timedelta(days=HISTORY_DAYS)
    for day_offset in range(HISTORY_DAYS):
        d = start_date + timedelta(days=day_offset)
        for shift_idx, (shift_label, _) in enumerate(SHIFT_DEFS):
            for m in MACHINES:
                start, end = _shift_window(d, shift_idx)
                # Realistic per-shift output around 60-100 tons depending on speed.
                base_tons = rng.uniform(60.0, 100.0)
                # Occasional bad shift drops output and OEE.
                if rng.random() < 0.05:
                    base_tons *= rng.uniform(0.4, 0.7)
                oee = rng.gauss(mu=m["current_oee_percent"], sigma=2.5)
                oee = max(60.0, min(98.5, oee))
                rows.append({
                    "run_id": f"run-{m['machine_id']}-{d.isoformat()}-{shift_label}",
                    "machine_id": m["machine_id"],
                    "start_time": start,
                    "end_time": end,
                    "product_grade": rng.choice(PRODUCT_GRADES),
                    "tons_produced": round(base_tons, 2),
                    "oee_percent": round(oee, 2),
                    "shift": shift_label,
                })
    return rows


def gen_maintenance_logs(rng: random.Random) -> list[dict]:
    """~50 logs per machine spread over 6 months. Component frequency reflects
    real wear patterns — Yankee blade swaps and ViscoNip felt changes dominate.
    """
    # Cadence (approximate days between events) and typical cost band per component.
    cadence: dict[str, tuple[int, tuple[int, int]]] = {
        "yankee":   (14, (8000, 18000)),
        "visconip": (28, (4000, 9000)),
        "aircap":   (45, (2500, 6000)),
        "headbox":  (60, (1500, 4000)),
        "softreel": (75, (1200, 3000)),
        "rewinder": (75, (1200, 3500)),
    }
    notes_by_component = {
        "yankee":   ["Replaced creping blade. Vibration baseline reset.",
                     "Yankee bearing inspection — within tolerance.",
                     "Blade pressure recalibration after grade change.",
                     "Replaced bearing set BR-7842 on bearing 3."],
        "visconip": ["Replaced press felt. Conditioning system flushed.",
                     "ViscoNip belt tension adjusted.",
                     "Shoe load profile recalibrated."],
        "aircap":   ["AirCap burner flame check.",
                     "Hood air filter replaced.",
                     "Heat recovery duct cleaned."],
        "headbox":  ["Dilution valve servicing.",
                     "Slice opening recalibrated.",
                     "Headbox consistency sensor cleaned."],
        "softreel": ["Reel drum bearing greased.", "Tension control retuned."],
        "rewinder": ["Log saw blade replacement.", "Glue applicator cleaned."],
    }

    rows: list[dict] = []
    counter = 0
    start_date = TODAY - timedelta(days=HISTORY_DAYS)
    for m in MACHINES:
        for component_id, (cad_days, (lo, hi)) in cadence.items():
            d = start_date + timedelta(days=rng.randint(0, cad_days))
            while d <= TODAY:
                counter += 1
                # Bias maintenance type — most are preventive on cadence,
                # with occasional corrective/predictive/emergency.
                roll = rng.random()
                if roll < 0.7:
                    mtype = "preventive"
                    downtime = round(rng.uniform(2.0, 6.0), 2)
                elif roll < 0.85:
                    mtype = "predictive"
                    downtime = round(rng.uniform(2.0, 5.0), 2)
                elif roll < 0.97:
                    mtype = "corrective"
                    downtime = round(rng.uniform(4.0, 10.0), 2)
                else:
                    mtype = "emergency"
                    downtime = round(rng.uniform(8.0, 24.0), 2)
                rows.append({
                    "log_id": f"mlog-{d.isoformat()}-{counter:04d}",
                    "machine_id": m["machine_id"],
                    "component_id": component_id,
                    "maintenance_type": mtype,
                    "date_performed": d,
                    "cost_usd": round(rng.uniform(lo, hi), 2),
                    "downtime_hours": downtime,
                    "technician": rng.choice(TECHNICIANS),
                    "notes": rng.choice(notes_by_component[component_id]),
                })
                d += timedelta(days=cad_days + rng.randint(-3, 5))
    return rows


def gen_alarm_events(rng: random.Random) -> list[dict]:
    """500+ alarms over 6 months with realistic severity distribution."""
    descriptions = {
        "info": [
            "Grade change initiated",
            "Shift handover logged",
            "Routine sensor calibration completed",
            "Stock cleaner cycle started",
        ],
        "warning": [
            "Yankee bearing 3 vibration above 5.0 mm/s threshold",
            "ViscoNip felt moisture below 35%",
            "AirCap inlet temperature rising trend detected",
            "Headbox stock temperature drift",
            "Reel tension fluctuation exceeded 5% band",
            "Steam pressure briefly outside 8-10 bar range",
        ],
        "critical": [
            "Yankee surface temperature deviation > 10°C",
            "Bearing 3 vibration exceeded 7.0 mm/s — failure imminent",
            "Loss of steam pressure — line stop triggered",
            "AirCap burner flameout event",
        ],
    }
    rows: list[dict] = []
    counter = 0
    start_dt = _utc(datetime.combine(TODAY - timedelta(days=HISTORY_DAYS), time(0, 0)))
    end_dt = _utc(datetime.combine(TODAY, time(0, 0)))
    span_seconds = int((end_dt - start_dt).total_seconds())
    target = 600
    severity_weights = [("info", 0.45), ("warning", 0.45), ("critical", 0.10)]
    severities, weights = zip(*severity_weights)
    for _ in range(target):
        ts = start_dt + timedelta(seconds=rng.randint(0, span_seconds))
        sev = rng.choices(severities, weights=weights, k=1)[0]
        m = rng.choice(MACHINES)
        # ~92% are resolved; rest stay open so active_alerts_count is non-zero.
        resolved = rng.random() < 0.92
        if resolved:
            resolved_at = ts + timedelta(minutes=rng.randint(5, 240))
            downtime = rng.randint(0, 90) if sev != "info" else 0
        else:
            resolved_at = None
            downtime = 0
        counter += 1
        rows.append({
            "alarm_id": f"alm-{ts.date().isoformat()}-{counter:04d}",
            "machine_id": m["machine_id"],
            "timestamp": ts,
            "severity": sev,
            "description": rng.choice(descriptions[sev]),
            "resolved_at": resolved_at,
            "downtime_minutes": downtime,
        })
    return rows


def gen_quality_scans(rng: random.Random, runs: list[dict]) -> Iterable[dict]:
    """One scan per hour of every production run (~8 per run, ~17k total).
    Yields rows so the bulk insert can stream them."""
    for run in runs:
        # Use a per-run baseline so values track sensibly within a shift.
        bw_base = rng.uniform(19.0, 25.0)
        moist_base = rng.uniform(4.5, 7.0)
        soft_base = rng.uniform(72.0, 88.0)
        cal_base = rng.uniform(95.0, 140.0)
        for hour in range(SHIFT_HOURS):
            ts = run["start_time"] + timedelta(hours=hour)
            yield {
                "scan_id": f"qs-{run['run_id']}-{hour:02d}",
                "run_id": run["run_id"],
                "timestamp": ts,
                "basis_weight_gsm": round(bw_base + rng.gauss(0, 0.4), 2),
                "moisture_percent": round(moist_base + rng.gauss(0, 0.25), 2),
                "softness_index":  round(max(60.0, min(95.0, soft_base + rng.gauss(0, 1.2))), 2),
                "caliper_microns": round(cal_base + rng.gauss(0, 3.0), 2),
            }


# --- Insert pipeline --------------------------------------------------------

INSERT_SQL = {
    "machines": text("""
        INSERT INTO machines (machine_id, name, location, installation_date, status,
                              current_speed_mpm, current_oee_percent)
        VALUES (:machine_id, :name, :location, :installation_date, :status,
                :current_speed_mpm, :current_oee_percent)
    """),
    "components": text("""
        INSERT INTO components (machine_id, component_id, name, is_critical,
                                expected_lifetime_hours, hours_since_last_maintenance,
                                last_maintenance_date)
        VALUES (:machine_id, :component_id, :name, :is_critical,
                :expected_lifetime_hours, :hours_since_last_maintenance,
                :last_maintenance_date)
    """),
    "production_runs": text("""
        INSERT INTO production_runs (run_id, machine_id, start_time, end_time,
                                     product_grade, tons_produced, oee_percent, shift)
        VALUES (:run_id, :machine_id, :start_time, :end_time,
                :product_grade, :tons_produced, :oee_percent, :shift)
    """),
    "maintenance_logs": text("""
        INSERT INTO maintenance_logs (log_id, machine_id, component_id, maintenance_type,
                                      date_performed, cost_usd, downtime_hours,
                                      technician, notes)
        VALUES (:log_id, :machine_id, :component_id, :maintenance_type,
                :date_performed, :cost_usd, :downtime_hours, :technician, :notes)
    """),
    "alarm_events": text("""
        INSERT INTO alarm_events (alarm_id, machine_id, timestamp, severity,
                                  description, resolved_at, downtime_minutes)
        VALUES (:alarm_id, :machine_id, :timestamp, :severity,
                :description, :resolved_at, :downtime_minutes)
    """),
    "quality_scans": text("""
        INSERT INTO quality_scans (scan_id, run_id, timestamp, basis_weight_gsm,
                                   moisture_percent, softness_index, caliper_microns)
        VALUES (:scan_id, :run_id, :timestamp, :basis_weight_gsm,
                :moisture_percent, :softness_index, :caliper_microns)
    """),
}


def _chunked(rows: Iterable[dict], size: int = 1000):
    chunk: list[dict] = []
    for r in rows:
        chunk.append(r)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit(
            "[seed] DATABASE_URL is not set. Export it before running, e.g.\n"
            "  export DATABASE_URL='postgresql://postgres:PASSWORD@db.<ref>.supabase.co:5432/postgres'"
        )
    print(f"[seed] connecting to {db_url.rsplit('@', 1)[-1]}")
    engine = create_engine(db_url, future=True)

    print("[seed] applying schema.sql")
    schema_sql = SCHEMA_PATH.read_text()
    with engine.begin() as conn:
        # psycopg2 accepts multiple statements via exec_driver_sql.
        conn.exec_driver_sql(schema_sql)

    rng = random.Random(42)

    machines = MACHINES
    components = gen_components()
    runs = gen_production_runs(rng)
    logs = gen_maintenance_logs(rng)
    alarms = gen_alarm_events(rng)

    counts: dict[str, int] = {}

    with engine.begin() as conn:
        conn.execute(INSERT_SQL["machines"], machines)
        counts["machines"] = len(machines)

        conn.execute(INSERT_SQL["components"], components)
        counts["components"] = len(components)

        for batch in _chunked(runs):
            conn.execute(INSERT_SQL["production_runs"], batch)
        counts["production_runs"] = len(runs)

        conn.execute(INSERT_SQL["maintenance_logs"], logs)
        counts["maintenance_logs"] = len(logs)

        conn.execute(INSERT_SQL["alarm_events"], alarms)
        counts["alarm_events"] = len(alarms)

        scans_total = 0
        for batch in _chunked(gen_quality_scans(rng, runs), size=2000):
            conn.execute(INSERT_SQL["quality_scans"], batch)
            scans_total += len(batch)
        counts["quality_scans"] = scans_total

        # Backfill components.last_maintenance_date and hours_since_last_maintenance
        # from the freshly-inserted maintenance_logs.
        conn.execute(text("""
            UPDATE components c
            SET last_maintenance_date = sub.last_date,
                hours_since_last_maintenance = GREATEST(
                    0,
                    (DATE :today - sub.last_date) * 24
                )
            FROM (
                SELECT machine_id, component_id, MAX(date_performed) AS last_date
                FROM maintenance_logs
                GROUP BY machine_id, component_id
            ) sub
            WHERE c.machine_id = sub.machine_id
              AND c.component_id = sub.component_id
        """), {"today": TODAY})

    total = sum(counts.values())
    print("[seed] inserted:")
    for table, n in counts.items():
        print(f"  {table:18s} {n:>7d}")
    print(f"  {'TOTAL':18s} {total:>7d}")

    if total < 10_000:
        raise SystemExit(f"[seed] FAILED: only {total} rows generated (need >= 10,000)")
    print("[seed] OK — exceeds 10,000-row target.")


if __name__ == "__main__":
    main()
