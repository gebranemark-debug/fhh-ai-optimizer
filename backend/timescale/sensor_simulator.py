"""Generate realistic 6-month sensor data for the 4 FHH machines and load it
into the ``sensor_readings`` hypertable defined in ``schema.sql``.

Sensor streams (8 per machine, 32 total) come straight out of the API
contract's sensor catalog (docs/API_CONTRACT-2.md §Sensor types):

    yankee_surface_temp           °C        100-120
    yankee_steam_pressure         bar       8-10
    yankee_vibration_bearing_1    mm/s      2-4
    yankee_vibration_bearing_2    mm/s      2-4
    yankee_vibration_bearing_3    mm/s      2-4
    visconip_nip_pressure         bar       4-6
    aircap_inlet_temp             °C        480-520
    rewinder_speed                m/min     1800-2222

The contract's ``qcs_softness_index`` lives at the Yankee creping stage but
is sampled by the IQ QCS scanner, not the DCS — it lives in
``quality_scans`` (PostgreSQL) and is intentionally NOT generated here.

Three labeled bearing-failure events are injected into the time series so
the ML layer in Prompt 3 has positive examples to learn from. Each event
ramps the corresponding ``yankee_vibration_bearing_*`` reading from normal
into "imminent failure" over a few weeks. Events are also written to the
``sensor_failure_events`` table.

Interval note: the prompt specifies "1-minute intervals" and "~1M rows"
which are inconsistent (1-min × 180 days × 32 sensors ≈ 8.3M rows). Default
here is 5-minute intervals (~1.66M rows) — dense enough that hourly ETL
aggregates have plenty of samples per bucket, sparse enough to load through
Supabase's Session Pooler without melting it. Override with
``--interval-seconds 60`` if you want literal 1-minute density.

Runs:
    python backend/timescale/sensor_simulator.py
    python backend/timescale/sensor_simulator.py --skip-schema
    python backend/timescale/sensor_simulator.py --interval-seconds 60
"""

from __future__ import annotations

import argparse
import math
import os
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine, text


# Anchor matches Prompt 1's seed_data.py so the time windows line up exactly.
TODAY = date(2026, 4, 25)
HISTORY_DAYS = 180
DEFAULT_INTERVAL_SECONDS = 300       # 5 minutes
DEFAULT_BATCH_SIZE = 5_000           # one transaction per batch (pooler-safe)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
DEFAULT_DB_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/fhh"

MACHINE_IDS = ["al-nakheel", "al-bardi", "al-sindian", "al-snobar"]


# =============================================================================
# Sensor catalog — one row per (component_id, sensor_type). Ranges match the
# API contract; means/sigmas are tuned to sit comfortably inside each range.
# =============================================================================

@dataclass(frozen=True)
class SensorSpec:
    sensor_type: str       # API-contract ID
    component_id: str      # populates sensor_readings.sensor_location
    unit: str
    mu: float              # baseline mean
    sigma: float           # per-sample noise
    diurnal_amp: float     # +/- diurnal swing on top of mu
    drift_per_day: float   # very slow background drift, mu/day


SENSORS: list[SensorSpec] = [
    # Yankee (the critical $20K/hr component — most sensors live here)
    SensorSpec("yankee_surface_temp",         "yankee",   "°C",    mu=110.0, sigma=1.2,  diurnal_amp=1.5,  drift_per_day=0.0),
    SensorSpec("yankee_steam_pressure",       "yankee",   "bar",   mu=9.0,   sigma=0.15, diurnal_amp=0.05, drift_per_day=0.0),
    SensorSpec("yankee_vibration_bearing_1",  "yankee",   "mm/s",  mu=3.0,   sigma=0.25, diurnal_amp=0.05, drift_per_day=0.0005),
    SensorSpec("yankee_vibration_bearing_2",  "yankee",   "mm/s",  mu=3.0,   sigma=0.25, diurnal_amp=0.05, drift_per_day=0.0005),
    SensorSpec("yankee_vibration_bearing_3",  "yankee",   "mm/s",  mu=3.0,   sigma=0.25, diurnal_amp=0.05, drift_per_day=0.0005),
    # ViscoNip
    SensorSpec("visconip_nip_pressure",       "visconip", "bar",   mu=5.0,   sigma=0.15, diurnal_amp=0.03, drift_per_day=0.0),
    # AirCap
    SensorSpec("aircap_inlet_temp",           "aircap",   "°C",    mu=500.0, sigma=4.0,  diurnal_amp=3.0,  drift_per_day=0.0),
    # Reel speed (the contract's "machine speed" stream is rewinder_speed)
    SensorSpec("rewinder_speed",              "rewinder", "m/min", mu=2050.0, sigma=18.0, diurnal_amp=8.0,  drift_per_day=0.0),
]


# =============================================================================
# Failure events — 3 labeled bearing-degradation windows over 180 days.
# Each ramps the chosen bearing's vibration from ~3.0 mm/s up to ~7.5+ mm/s
# (well past the contract's 5.0 mm/s warning threshold) over RAMP_DAYS, then
# drops back after the failure_time (post-replacement).
# =============================================================================

RAMP_DAYS = 18  # weeks of rising vibration before the event
FAILURE_VIB_PEAK = 7.6  # mm/s at the moment of failure


@dataclass(frozen=True)
class FailureEvent:
    event_id: str
    machine_id: str
    component_id: str
    sensor_type: str          # which bearing
    degradation_start: datetime
    failure_time: datetime
    failure_mode: str
    description: str


def _build_failure_events() -> list[FailureEvent]:
    """Three deterministic events spread across the 6-month window."""
    start = datetime.combine(TODAY - timedelta(days=HISTORY_DAYS), time(0, 0), tzinfo=timezone.utc)
    end = datetime.combine(TODAY, time(0, 0), tzinfo=timezone.utc)
    span = (end - start).total_seconds()

    # Three failure timestamps placed at roughly 25%, 55%, 88% of the window.
    placements = [0.25, 0.55, 0.88]
    targets = [
        ("al-bardi",   "yankee_vibration_bearing_2", "bearing_fatigue",
         "Bearing 2 fatigue — replaced after vibration crossed 7 mm/s"),
        ("al-sindian", "yankee_vibration_bearing_3", "bearing_lubrication_loss",
         "Bearing 3 lubrication starvation — caught before catastrophic failure"),
        ("al-nakheel", "yankee_vibration_bearing_3", "bearing_fatigue",
         "Bearing 3 fatigue — RMS rising 0.4 mm/s/day for 11 days"),
    ]

    events: list[FailureEvent] = []
    for i, ((machine_id, sensor_type, mode, desc), pct) in enumerate(zip(targets, placements), start=1):
        failure_time = start + timedelta(seconds=span * pct)
        degradation_start = failure_time - timedelta(days=RAMP_DAYS)
        events.append(FailureEvent(
            event_id=f"fail-{i:03d}-{machine_id}-{sensor_type}",
            machine_id=machine_id,
            component_id="yankee",
            sensor_type=sensor_type,
            degradation_start=degradation_start,
            failure_time=failure_time,
            failure_mode=mode,
            description=desc,
        ))
    return events


def _failure_overlay(spec: SensorSpec, machine_id: str, ts: datetime,
                     events: list[FailureEvent]) -> float:
    """If ``ts`` falls inside a degradation window for this (machine, sensor),
    return an additive overlay that ramps the value toward FAILURE_VIB_PEAK.
    Returns 0.0 otherwise."""
    for ev in events:
        if ev.machine_id != machine_id or ev.sensor_type != spec.sensor_type:
            continue
        if ts < ev.degradation_start or ts > ev.failure_time:
            continue
        # Linear ramp from 0 at degradation_start to (peak - mu) at failure_time.
        progress = (ts - ev.degradation_start).total_seconds() / max(
            1.0, (ev.failure_time - ev.degradation_start).total_seconds()
        )
        return (FAILURE_VIB_PEAK - spec.mu) * progress
    return 0.0


# =============================================================================
# Generator — yields one sensor_readings row at a time so we never hold the
# full ~1.66M-row dataset in memory.
# =============================================================================

def gen_sensor_readings(
    rng: random.Random,
    interval_seconds: int,
    failure_events: list[FailureEvent],
) -> Iterable[dict]:
    start_dt = datetime.combine(TODAY - timedelta(days=HISTORY_DAYS), time(0, 0), tzinfo=timezone.utc)
    end_dt = datetime.combine(TODAY, time(0, 0), tzinfo=timezone.utc)
    step = timedelta(seconds=interval_seconds)
    seconds_per_day = 86_400.0

    ts = start_dt
    while ts < end_dt:
        # Diurnal phase shared across sensors at this timestamp.
        seconds_into_day = (ts.hour * 3600 + ts.minute * 60 + ts.second) % seconds_per_day
        diurnal_phase = math.sin(2 * math.pi * seconds_into_day / seconds_per_day)
        days_since_start = (ts - start_dt).total_seconds() / seconds_per_day

        for machine_id in MACHINE_IDS:
            for spec in SENSORS:
                value = (
                    spec.mu
                    + spec.diurnal_amp * diurnal_phase
                    + spec.drift_per_day * days_since_start
                    + rng.gauss(0.0, spec.sigma)
                    + _failure_overlay(spec, machine_id, ts, failure_events)
                )
                yield {
                    "timestamp": ts,
                    "machine_id": machine_id,
                    "sensor_type": spec.sensor_type,
                    "sensor_location": spec.component_id,
                    "value": round(value, 4),
                    "unit": spec.unit,
                }
        ts += step


# =============================================================================
# Insert pipeline — same per-batch transaction pattern as the PostgreSQL seed,
# so Supabase's Session Pooler stays happy.
# =============================================================================

INSERT_READING_SQL = text("""
    INSERT INTO sensor_readings
        ("timestamp", machine_id, sensor_type, sensor_location, value, unit)
    VALUES
        (:timestamp, :machine_id, :sensor_type, :sensor_location, :value, :unit)
""")

INSERT_EVENT_SQL = text("""
    INSERT INTO sensor_failure_events
        (event_id, machine_id, component_id, sensor_type,
         degradation_start, failure_time, failure_mode, description)
    VALUES
        (:event_id, :machine_id, :component_id, :sensor_type,
         :degradation_start, :failure_time, :failure_mode, :description)
""")


def _truncate_data_tables(engine) -> None:
    print("[sim]  --skip-schema: truncating sensor_readings + sensor_failure_events")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "TRUNCATE TABLE sensor_readings, sensor_failure_events RESTART IDENTITY"
        )


def _insert_batched(engine, sql, rows: Iterable[dict], label: str,
                    batch_size: int) -> int:
    inserted = 0
    chunk: list[dict] = []
    for r in rows:
        chunk.append(r)
        if len(chunk) >= batch_size:
            with engine.begin() as conn:
                conn.execute(sql, chunk)
            inserted += len(chunk)
            chunk = []
            print(f"  [{label:18s}] {inserted:>9d} rows committed")
    if chunk:
        with engine.begin() as conn:
            conn.execute(sql, chunk)
        inserted += len(chunk)
        print(f"  [{label:18s}] {inserted:>9d} rows committed (final)")
    return inserted


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate FHH sensor data for TimescaleDB.")
    p.add_argument("--skip-schema", action="store_true",
                   help="Skip applying schema.sql; truncate data tables instead.")
    p.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS,
                   help=f"Sample interval in seconds (default {DEFAULT_INTERVAL_SECONDS} = 5 min). "
                        "Use 60 for literal 1-minute density (~8.3M rows).")
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                   help=f"Rows per commit (default {DEFAULT_BATCH_SIZE}).")
    return p.parse_args()


def expected_row_count(interval_seconds: int) -> int:
    """Used by tests/README — keeps the math in one place."""
    samples_per_machine = (HISTORY_DAYS * 86_400) // interval_seconds
    return samples_per_machine * len(MACHINE_IDS) * len(SENSORS)


def main() -> None:
    args = _parse_args()
    db_url = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    print(f"[sim]  connecting to {db_url.rsplit('@', 1)[-1]}")
    print(f"[sim]  interval={args.interval_seconds}s  batch_size={args.batch_size}")
    print(f"[sim]  expected sensor_readings rows: {expected_row_count(args.interval_seconds):,}")

    engine = create_engine(db_url, future=True)

    if args.skip_schema:
        print("[sim]  skipping schema.sql")
        _truncate_data_tables(engine)
    else:
        print("[sim]  applying schema.sql")
        with engine.begin() as conn:
            conn.exec_driver_sql(SCHEMA_PATH.read_text())

    rng = random.Random(42)  # match Prompt 1's seed for reproducibility
    failure_events = _build_failure_events()

    # 1) Failure events first (small) — gives the readings a label set to point at.
    n_events = _insert_batched(
        engine, INSERT_EVENT_SQL,
        [ev.__dict__ for ev in failure_events],
        "failure_events",
        batch_size=args.batch_size,
    )

    # 2) Stream sensor readings, batched.
    n_readings = _insert_batched(
        engine, INSERT_READING_SQL,
        gen_sensor_readings(rng, args.interval_seconds, failure_events),
        "sensor_readings",
        batch_size=args.batch_size,
    )

    print("[sim]  inserted:")
    print(f"  sensor_failure_events  {n_events:>9d}")
    print(f"  sensor_readings        {n_readings:>9d}")
    print("[sim]  OK.")


if __name__ == "__main__":
    main()
