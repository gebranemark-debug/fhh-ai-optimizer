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
    # Default: write to TimescaleDB (Supabase or local).
    python backend/timescale/sensor_simulator.py
    python backend/timescale/sensor_simulator.py --skip-schema

    # In-memory only — never opens a DB connection. Used by the
    # `etl.py --in-memory` demo path so we can skip the slow DB inserts
    # entirely. Optional --out drops the raw frame to parquet/csv.
    python backend/timescale/sensor_simulator.py --in-memory
    python backend/timescale/sensor_simulator.py --in-memory --out raw.parquet

    # Override interval (default 5 min).
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
    p.add_argument("--in-memory", action="store_true",
                   help="Generate the dataset in-memory only (no DB writes). "
                        "Use this when DB inserts are too slow (e.g. Supabase Session "
                        "Pooler throttling). Combine with --out to save a parquet/csv.")
    p.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS,
                   help=f"Sample interval in seconds (default {DEFAULT_INTERVAL_SECONDS} = 5 min). "
                        "Use 60 for literal 1-minute density (~8.3M rows).")
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                   help=f"Rows per commit when writing to DB (default {DEFAULT_BATCH_SIZE}).")
    p.add_argument("--out", type=str, default=None,
                   help="Optional output path for --in-memory mode. "
                        "Suffix .parquet or .csv decides the format.")
    return p.parse_args()


def expected_row_count(interval_seconds: int) -> int:
    """Used by tests/README — keeps the math in one place."""
    samples_per_machine = (HISTORY_DAYS * 86_400) // interval_seconds
    return samples_per_machine * len(MACHINE_IDS) * len(SENSORS)


def simulate_to_dataframe(
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    seed: int = 42,
):
    """In-memory dataset generation. Returns ``(readings_df, events_df)``.

    Same deterministic output as the DB-insert path — same seed, same anchor,
    same failure events. ``etl.py --in-memory`` calls this so the whole
    pipeline can run without ever touching TimescaleDB.

    Returns:
      readings_df: columns timestamp, machine_id, sensor_type, sensor_location,
                   value, unit. ~1.66M rows at 5-min default.
      events_df:   columns matching sensor_failure_events table. 3 rows.
    """
    # Local import so this module stays usable without pandas installed when
    # running the DB-only path.
    import pandas as pd

    rng = random.Random(seed)
    failure_events = _build_failure_events()

    readings_df = pd.DataFrame.from_records(
        gen_sensor_readings(rng, interval_seconds, failure_events),
        columns=["timestamp", "machine_id", "sensor_type", "sensor_location",
                 "value", "unit"],
    )
    # Ensure tz-aware timestamps survive the DataFrame conversion.
    readings_df["timestamp"] = pd.to_datetime(readings_df["timestamp"], utc=True)

    events_df = pd.DataFrame([{
        "event_id": ev.event_id,
        "machine_id": ev.machine_id,
        "component_id": ev.component_id,
        "sensor_type": ev.sensor_type,
        "degradation_start": pd.Timestamp(ev.degradation_start),
        "failure_time":      pd.Timestamp(ev.failure_time),
        "failure_mode": ev.failure_mode,
        "description": ev.description,
    } for ev in failure_events])

    return readings_df, events_df


def main() -> None:
    args = _parse_args()
    print(f"[sim]  interval={args.interval_seconds}s  "
          f"expected sensor_readings rows: {expected_row_count(args.interval_seconds):,}")

    if args.in_memory:
        # In-memory mode: never opens a DB connection. Useful for the demo
        # workflow where Supabase pooler insert throughput is the bottleneck.
        from pathlib import Path
        print("[sim]  --in-memory: generating dataset as a pandas DataFrame")
        readings_df, events_df = simulate_to_dataframe(
            interval_seconds=args.interval_seconds, seed=42,
        )
        print(f"[sim]  sensor_readings rows in memory:        {len(readings_df):,}")
        print(f"[sim]  sensor_failure_events rows in memory:  {len(events_df):,}")

        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.suffix.lower() == ".parquet":
                readings_df.to_parquet(out, index=False)
            else:
                readings_df.to_csv(out, index=False)
            events_path = out.with_name(out.stem + "_failure_events" + out.suffix)
            if out.suffix.lower() == ".parquet":
                events_df.to_parquet(events_path, index=False)
            else:
                events_df.to_csv(events_path, index=False)
            print(f"[sim]  wrote sensor_readings → {out}")
            print(f"[sim]  wrote sensor_failure_events → {events_path}")
        print("[sim]  OK (in-memory).")
        return

    db_url = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    print(f"[sim]  connecting to {db_url.rsplit('@', 1)[-1]}")
    print(f"[sim]  batch_size={args.batch_size}")
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


# =============================================================================
# Yearly raw layer — production-mirror of what Valmet DNA DCS would stream:
# per-minute wide-format snapshots (one row per (timestamp, machine_id) with
# 8 sensor value columns). 4 machines × 1440 min/day × 365 days = ~2.1M rows.
#
# This is the raw layer in the three-tier architecture from
# docs/fhh_database_architecture.pdf:
#   raw (per-minute, this file)  →  feature (hourly, etl.py)  →  model
#
# By implementing all three layers — even though only the feature layer is
# used for training — the pipeline is validated at production scale and the
# Oracle ADW connector swap point is real instead of theoretical.
# =============================================================================

YEARLY_TODAY = date(2026, 4, 25)
YEARLY_DAYS = 365
YEARLY_INTERVAL_SECONDS = 60  # per-minute density
# Spread across 4 machines × 6 sensor types. Tuned to land the
# target_failure_within_72h positive count in [800, 1500] after ETL
# labelling — each event labels ~73 hour-buckets, so 16 events give
# ≈1,168 positives. Higher counts cause label overlap that pushes the
# positive rate past 50% and the model collapses to a trivial classifier.
# (The minute-resolution PRECURSOR window stays rich: 16 events with
# 5-10 day precursors = 100,000+ minute-readings of degradation signal.)
YEARLY_FAILURE_EVENT_COUNT = 16

# Eligible sensor types per failure mode. Each mode draws from one or more
# physical sensors; bearings have three options, the others one each. The
# `peak` is the value the sensor ramps to at failure_time (well beyond the
# normal range so trend / std features pick it up cleanly).
_FAILURE_MODE_POOL = {
    "bearing_fatigue":  [
        ("yankee_vibration_bearing_1", 7.5),
        ("yankee_vibration_bearing_2", 7.5),
        ("yankee_vibration_bearing_3", 7.5),
    ],
    "thermal_runaway":  [("yankee_surface_temp",   125.0)],
    "pressure_anomaly": [("yankee_steam_pressure", 11.5)],
    "fan_drift":        [("aircap_inlet_temp",     535.0)],
}

# Flat lookup: sensor_type -> peak value (used by the generator inside
# generate_yearly_raw_parquet to apply ramps).
_PEAK_BY_SENSOR = {
    sensor: peak
    for pool in _FAILURE_MODE_POOL.values()
    for sensor, peak in pool
}

YEARLY_PRECURSOR_DAYS_MIN = 5
YEARLY_PRECURSOR_DAYS_MAX = 10


# =============================================================================
# Realistic-noise controls. Each constant is independently dialable so we can
# tune metrics without rewriting code: set any to 0 / False to disable that
# factor entirely. Tuned slightly milder than max realism so the supervised
# model still hits the demo targets (Precision ≥0.75, Recall ≥0.80).
# =============================================================================

# 1. False-alarm spikes: workers / equipment cause brief sensor spikes that
#    are NOT real failure precursors. Distributed across (machine, sensor)
#    pairs and kept clear of real precursor windows so they challenge the
#    model's precision rather than masking real failures.
NOISE_FALSE_ALARM_COUNT = 100      # set to 0 to disable
NOISE_FALSE_ALARM_DURATION_MIN = 1 # samples (1-min granularity → 30-90s)
NOISE_FALSE_ALARM_DURATION_MAX = 2
NOISE_FALSE_ALARM_AMPLITUDE_FRAC = 0.50  # spike size as fraction of normal range

# 2. Sensor drift: each sensor's baseline slowly walks ±NOISE_DRIFT_PERCENT
#    of its normal range over months, then snaps back at recalibration days
#    (every NOISE_DRIFT_RECAL_INTERVAL_DAYS_* range).
NOISE_DRIFT_PERCENT = 0.08         # set to 0 to disable
NOISE_DRIFT_RECAL_INTERVAL_DAYS_MIN = 90
NOISE_DRIFT_RECAL_INTERVAL_DAYS_MAX = 120

# 3. Operating regime shifts: each machine runs different products in 5-15
#    day blocks. Each product has a small offset per sensor.
NOISE_PRODUCT_REGIMES = True       # set to False to use facial_tissue baseline always
NOISE_PRODUCT_BLOCK_DAYS_MIN = 5
NOISE_PRODUCT_BLOCK_DAYS_MAX = 15

PRODUCT_TYPES = ["facial_tissue", "toilet_paper", "kitchen_towel", "napkin"]

# Per-product additive offsets (in the sensor's native units). facial_tissue
# is the reference baseline (no offset). Values calibrated to be smaller
# than failure-precursor deltas so the model can still pick out failures.
PRODUCT_SENSOR_OFFSETS: dict[str, dict[str, float]] = {
    "facial_tissue":  {},
    "toilet_paper": {
        "rewinder_speed":              61.5,    # +3% of 2050
        "yankee_surface_temp":          2.0,
        "yankee_vibration_bearing_1":   0.05,
        "yankee_vibration_bearing_2":   0.05,
        "yankee_vibration_bearing_3":   0.05,
    },
    "kitchen_towel": {
        "rewinder_speed":            -102.5,    # -5% of 2050
        "yankee_surface_temp":          5.0,
        "yankee_vibration_bearing_1":  -0.05,
        "yankee_vibration_bearing_2":  -0.05,
        "yankee_vibration_bearing_3":  -0.05,
    },
    "napkin": {
        "rewinder_speed":             102.5,    # +5%
    },
}

# 4. No-warning failures: a fraction of failure events have no precursor
#    ramp — the sensor reads normal until the failure moment. The label
#    set still records them; the model is forced to either pick them up
#    from indirect cues (e.g. anomaly score on related sensors) or accept
#    the recall hit. Marked in the events parquet via ``precursor_type``.
NOISE_NO_WARNING_FRACTION = 0.12   # set to 0 for all-precursor failures

# 5. Label noise (applied in etl.py, not here — surfaced for visibility).
#    A small fraction of target_failure_within_72h labels are flipped to
#    simulate maintenance-log mistakes.
NOISE_LABEL_NOISE_PERCENT = 0.03   # set to 0 to disable in the ETL


# -- Helpers -----------------------------------------------------------------

def _sensor_range_width(spec: SensorSpec) -> float:
    """Normal range width per spec — used for noise amplitudes that scale
    with the sensor's physical scale."""
    # The simulator's spec.mu is the centre of the normal range; the
    # contract's range is roughly ±10% of mu for most sensors. Fall back
    # to that when we don't have an explicit width.
    return abs(spec.diurnal_amp * 4.0) if spec.diurnal_amp else max(1.0, abs(spec.mu) * 0.05)


def _build_product_schedule(
    rng: random.Random,
    total_days: int,
) -> list[tuple[int, int, str]]:
    """Per-machine deterministic schedule of (start_day, end_day, product).
    Blocks are 5-15 days long; products are sampled uniformly so each
    machine sees a varied mix over the year."""
    schedule: list[tuple[int, int, str]] = []
    day = 0
    while day < total_days:
        block_len = rng.randint(NOISE_PRODUCT_BLOCK_DAYS_MIN, NOISE_PRODUCT_BLOCK_DAYS_MAX)
        product = rng.choice(PRODUCT_TYPES)
        schedule.append((day, min(day + block_len, total_days), product))
        day += block_len
    return schedule


def _expand_schedule_per_minute(
    schedule: list[tuple[int, int, str]],
    n_minutes: int,
):
    """Convert a day-block schedule to a per-minute string array."""
    import numpy as np
    out = np.empty(n_minutes, dtype=object)
    for start_day, end_day, product in schedule:
        start_idx = start_day * 1440
        end_idx = min(end_day * 1440, n_minutes)
        out[start_idx:end_idx] = product
    return out


def _build_drift_overlay(
    np_rng,
    range_width: float,
    n_days: int,
    n_minutes: int,
):
    """Build a per-minute drift overlay for one sensor. The drift is a
    daily random walk capped at ±NOISE_DRIFT_PERCENT × range_width, with
    full-reset events at random intervals every 90-120 days simulating
    field recalibration."""
    import numpy as np
    if NOISE_DRIFT_PERCENT <= 0:
        return np.zeros(n_minutes, dtype=np.float64)

    # Daily increments: small Gaussian steps. Step size scales so a year's
    # accumulation lands in the same order as the cap.
    step_sigma = NOISE_DRIFT_PERCENT * range_width / math.sqrt(n_days) * 1.5
    daily_steps = np_rng.normal(0.0, step_sigma, n_days)
    cumulative = np.cumsum(daily_steps)

    # Recalibration days — snap drift back to 0 from that day forward.
    recal_days: list[int] = []
    nxt = int(np_rng.integers(NOISE_DRIFT_RECAL_INTERVAL_DAYS_MIN,
                              NOISE_DRIFT_RECAL_INTERVAL_DAYS_MAX + 1))
    while nxt < n_days:
        recal_days.append(nxt)
        nxt += int(np_rng.integers(NOISE_DRIFT_RECAL_INTERVAL_DAYS_MIN,
                                   NOISE_DRIFT_RECAL_INTERVAL_DAYS_MAX + 1))
    for r in recal_days:
        cumulative[r:] -= cumulative[r]

    cap = NOISE_DRIFT_PERCENT * range_width
    cumulative = np.clip(cumulative, -cap, cap)
    return np.repeat(cumulative, 1440)[:n_minutes]


def _build_false_alarm_overlay(
    rng: random.Random,
    n_minutes: int,
    range_width: float,
    n_spikes: int,
    protected_ranges: list[tuple[int, int]],
    ts_int,
):
    """Per-(machine, sensor) overlay of n_spikes brief positive spikes
    (1-2 samples each) that are not real failures. Avoids the protected
    ranges around real failure precursors so the spikes don't accidentally
    land where the labels say a failure is imminent."""
    import numpy as np
    overlay = np.zeros(n_minutes, dtype=np.float64)
    if n_spikes <= 0:
        return overlay
    amp = NOISE_FALSE_ALARM_AMPLITUDE_FRAC * range_width
    placed = 0
    attempts = 0
    while placed < n_spikes and attempts < n_spikes * 30:
        attempts += 1
        t_idx = rng.randint(0, n_minutes - NOISE_FALSE_ALARM_DURATION_MAX - 1)
        t_int = int(ts_int[t_idx])
        if any(ds <= t_int <= ft for ds, ft in protected_ranges):
            continue
        dur = rng.randint(NOISE_FALSE_ALARM_DURATION_MIN,
                          NOISE_FALSE_ALARM_DURATION_MAX)
        overlay[t_idx:t_idx + dur] += amp
        placed += 1
    return overlay


def _build_yearly_failure_events(rng: random.Random) -> list[dict]:
    """Generate ``YEARLY_FAILURE_EVENT_COUNT`` deterministic failure events
    stratified so all 4 failure modes appear on every machine. With 16
    events that's 4 modes × 4 machines = 1 event per (machine, mode);
    larger counts repeat the rotation. Each event has a 5-10 day
    precursor during which the affected sensor ramps from baseline to
    peak; ETL labels the 73 hour-buckets ending at failure_time as
    target_failure_within_72h=1."""
    start_dt = datetime.combine(YEARLY_TODAY - timedelta(days=YEARLY_DAYS), time(0, 0), tzinfo=timezone.utc)
    end_dt   = datetime.combine(YEARLY_TODAY, time(0, 0), tzinfo=timezone.utc)
    span_seconds = int((end_dt - start_dt).total_seconds())

    modes = list(_FAILURE_MODE_POOL.keys())
    sensor_to_component = {
        "yankee_vibration_bearing_1": "yankee",
        "yankee_vibration_bearing_2": "yankee",
        "yankee_vibration_bearing_3": "yankee",
        "yankee_surface_temp":        "yankee",
        "yankee_steam_pressure":      "yankee",
        "aircap_inlet_temp":          "aircap",
    }

    events: list[dict] = []
    counter = 0
    # Stratified round-robin: each (machine, mode) pair gets exactly
    # ``per_pair`` events. With YEARLY_FAILURE_EVENT_COUNT=16 and 16
    # pairs, that's 1 each.
    n_pairs = len(MACHINE_IDS) * len(modes)
    per_pair = max(1, YEARLY_FAILURE_EVENT_COUNT // n_pairs)
    for machine_id in MACHINE_IDS:
        for mode in modes:
            for _ in range(per_pair):
                sensor_type, peak = rng.choice(_FAILURE_MODE_POOL[mode])
                # failure_time uniform within the year, leaving a 12-day
                # buffer at the start so 5-10 day precursors don't fall
                # outside the simulated window.
                failure_offset = rng.randint(int(86400 * 12), span_seconds - 1)
                failure_time = start_dt + timedelta(seconds=failure_offset)
                precursor_days = rng.randint(YEARLY_PRECURSOR_DAYS_MIN, YEARLY_PRECURSOR_DAYS_MAX)
                degradation_start = failure_time - timedelta(days=precursor_days)
                counter += 1
                events.append({
                    "event_id": f"fyr-{counter:04d}-{machine_id}-{sensor_type}",
                    "machine_id": machine_id,
                    "component_id": sensor_to_component[sensor_type],
                    "sensor_type": sensor_type,
                    "degradation_start": degradation_start,
                    "failure_time": failure_time,
                    "failure_mode": mode,
                    "description": f"{sensor_type} {mode} on {machine_id}",
                    # Default — the next pass below converts a fraction
                    # to "sudden" (no-precursor) failures.
                    "precursor_type": "gradual",
                })

    # Mark NOISE_NO_WARNING_FRACTION of events as "sudden" — the raw sensor
    # data shows nothing unusual until failure_time. The label set still
    # records the failure, so the model's recall takes the hit unless it
    # learns to lean on indirect cues. Distribute across distinct machines
    # so no single machine carries every no-warning event.
    if NOISE_NO_WARNING_FRACTION > 0 and events:
        n_sudden = max(1, int(round(len(events) * NOISE_NO_WARNING_FRACTION)))
        # Group event indices by machine so we can pull one-per-machine.
        by_machine: dict[str, list[int]] = {m: [] for m in MACHINE_IDS}
        for i, ev in enumerate(events):
            by_machine[ev["machine_id"]].append(i)
        machines_cycle = list(MACHINE_IDS)
        rng.shuffle(machines_cycle)
        chosen: list[int] = []
        for mid in machines_cycle:
            if len(chosen) >= n_sudden:
                break
            if not by_machine[mid]:
                continue
            chosen.append(rng.choice(by_machine[mid]))
        for idx in chosen:
            events[idx]["precursor_type"] = "sudden"

    return events


def generate_yearly_raw_parquet(
    out_path: Path,
    events_out_path: Path,
    seed: int = 42,
) -> tuple[int, int]:
    """Produce sensor_readings_raw.parquet (wide format, per-minute, full
    year) and sensor_failure_events.parquet (label set for the ETL).

    Returns (n_reading_rows, n_events).
    """
    import numpy as np
    import pandas as pd

    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    # -- timestamps -------------------------------------------------------
    start_ts = pd.Timestamp(YEARLY_TODAY - timedelta(days=YEARLY_DAYS), tz="UTC")
    end_ts   = pd.Timestamp(YEARLY_TODAY, tz="UTC")
    timestamps = pd.date_range(start_ts, end_ts, freq="1min", inclusive="left")
    n = len(timestamps)
    print(f"[yr]  timestamps: {n:,} per minute over {YEARLY_DAYS} days")

    # -- failure events ---------------------------------------------------
    events = _build_yearly_failure_events(rng)
    events_df = pd.DataFrame(events)
    events_df["degradation_start"] = pd.to_datetime(events_df["degradation_start"], utc=True)
    events_df["failure_time"]      = pd.to_datetime(events_df["failure_time"], utc=True)
    print(f"[yr]  failure events: {len(events_df):,}")
    per_machine = events_df["machine_id"].value_counts().to_dict()
    print(f"[yr]  per machine: {per_machine}")

    # Pre-compute timestamp epoch seconds for vectorized event masking.
    # Cast through datetime64[s] explicitly so this is robust to whatever
    # resolution the underlying numpy/pandas chose (date_range gives ns,
    # parquet round-trip gives us — they don't divide by the same factor).
    ts_int = timestamps.to_numpy().astype("datetime64[s]").astype("int64")
    seconds_into_day = (ts_int % 86400).astype(np.float64)
    diurnal_phase = np.sin(2 * np.pi * seconds_into_day / 86400.0)

    # -- per-machine generation ------------------------------------------
    spikes_per_pair = NOISE_FALSE_ALARM_COUNT // (len(MACHINE_IDS) * len(SENSORS))

    frames: list[pd.DataFrame] = []
    for machine_id in MACHINE_IDS:
        # Build per-machine product schedule (always — the column lands in
        # the parquet so the ETL can read it. When the regimes constant is
        # off, every minute reads "facial_tissue").
        if NOISE_PRODUCT_REGIMES:
            schedule = _build_product_schedule(rng, YEARLY_DAYS)
            product_per_minute = _expand_schedule_per_minute(schedule, n)
        else:
            product_per_minute = np.full(n, "facial_tissue", dtype=object)

        cols: dict = {
            "timestamp":      timestamps,
            "machine_id":     np.full(n, machine_id, dtype=object),
            "product_active": product_per_minute,
        }
        machine_events = events_df[events_df["machine_id"] == machine_id]

        # Pre-compute per-product offset masks for vectorized application
        # below. mask[product] == True at minute i iff that product was
        # active at minute i.
        product_masks = {
            p: (product_per_minute == p) for p in PRODUCT_TYPES
        }

        # Protected ranges (in epoch seconds) around real precursors —
        # used to keep false-alarm spikes from landing on top of real
        # failure windows where they'd corrupt the labels.
        protected_ranges: list[tuple[int, int]] = []
        for _, ev in machine_events.iterrows():
            ds = int(pd.Timestamp(ev["degradation_start"]).timestamp()) - 2 * 86400
            ft = int(pd.Timestamp(ev["failure_time"]).timestamp()) + 2 * 86400
            protected_ranges.append((ds, ft))

        for spec in SENSORS:
            base = (
                np.full(n, spec.mu, dtype=np.float64)
                + spec.diurnal_amp * diurnal_phase
                + np_rng.normal(0.0, spec.sigma, n)
            )

            # NOISE 3: product-regime offsets per minute.
            if NOISE_PRODUCT_REGIMES:
                for product, mask in product_masks.items():
                    offset = PRODUCT_SENSOR_OFFSETS.get(product, {}).get(spec.sensor_type, 0.0)
                    if offset and mask.any():
                        base[mask] += offset

            # NOISE 2: slow drift + recalibration snap-backs.
            range_width = _sensor_range_width(spec)
            drift = _build_drift_overlay(np_rng, range_width, YEARLY_DAYS, n)
            base = base + drift

            # Failure overlays: ramp from 0 at degradation_start to
            # (peak - mu) at failure_time. ``sudden`` events are skipped
            # so the raw sensor reads normal until failure_time (the
            # NOISE 4 path).
            overlay = np.zeros(n, dtype=np.float64)
            sensor_events = machine_events[machine_events["sensor_type"] == spec.sensor_type]
            sensor_events = sensor_events[sensor_events["precursor_type"] == "gradual"]
            if not sensor_events.empty:
                deg_starts_int = sensor_events["degradation_start"].to_numpy().astype("datetime64[s]").astype("int64")
                fail_times_int = sensor_events["failure_time"].to_numpy().astype("datetime64[s]").astype("int64")
                pk = _PEAK_BY_SENSOR[spec.sensor_type]
                for ds_int, ft_int in zip(deg_starts_int, fail_times_int):
                    mask = (ts_int >= ds_int) & (ts_int <= ft_int)
                    if not mask.any():
                        continue
                    progress = (ts_int[mask] - ds_int) / max(1.0, float(ft_int - ds_int))
                    ramp = (pk - spec.mu) * progress
                    overlay[mask] = np.maximum(overlay[mask], ramp)

            # NOISE 1: false-alarm spikes (added on top of overlay so the
            # sensor reads briefly elevated even if there's no failure).
            spike_overlay = _build_false_alarm_overlay(
                rng, n, range_width, spikes_per_pair, protected_ranges, ts_int,
            )
            cols[spec.sensor_type] = (base + overlay + spike_overlay).astype(np.float32)

        frames.append(pd.DataFrame(cols))
        n_sudden = int((machine_events["precursor_type"] == "sudden").sum())
        print(f"[yr]  generated {machine_id}: {n:,} rows  "
              f"({n_sudden} sudden / {len(machine_events) - n_sudden} gradual events)")

    df = pd.concat(frames, ignore_index=True)
    print(f"[yr]  combined wide-format frame: {len(df):,} rows × {df.shape[1]} cols")

    # -- write -----------------------------------------------------------
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False, compression="snappy")
    events_df.to_parquet(events_out_path, index=False, compression="snappy")

    raw_size_mb = out_path.stat().st_size / (1024 * 1024)
    events_size_kb = events_out_path.stat().st_size / 1024
    print(f"[yr]  wrote raw    → {out_path} ({raw_size_mb:.2f} MB)")
    print(f"[yr]  wrote events → {events_out_path} ({events_size_kb:.1f} KB)")
    return len(df), len(events_df)


def _yearly_main() -> None:
    """Entry point for the --yearly-raw CLI flag."""
    here = Path(__file__).parent
    raw_path = here / "sensor_readings_raw.parquet"
    events_path = here / "sensor_failure_events.parquet"
    n_rows, n_events = generate_yearly_raw_parquet(raw_path, events_path)
    print(f"[yr]  OK — {n_rows:,} readings, {n_events:,} events.")


if __name__ == "__main__":
    import sys
    if "--yearly-raw" in sys.argv:
        _yearly_main()
    else:
        main()
