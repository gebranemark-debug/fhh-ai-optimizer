"""ETL pipeline that turns raw sensor + relational data into an ML-ready
feature dataset for the FHH predictive-maintenance model.

Reads:
  - sensor_readings        from TimescaleDB (this layer)
  - sensor_failure_events  from TimescaleDB (this layer)  → builds the label
  - production_runs        from PostgreSQL  (Prompt 1 layer)
  - maintenance_logs       from PostgreSQL  (Prompt 1 layer)
  - components             from PostgreSQL  (Prompt 1 layer)

Produces a pandas DataFrame at hourly resolution, one row per
(machine_id, hour_bucket), with the feature columns called out in
docs/fhh_database_architecture.pdf "WHAT THE ML MODEL NEEDS AS INPUT":

    Feature                                       Source
    ---------------------------------------------------------
    yankee_surface_temp_avg                       sensor_readings
    yankee_surface_temp_max                       sensor_readings
    yankee_surface_temp_std                       sensor_readings
    temperature_deviation_from_baseline           computed
    yankee_vibration_bearing_{1,2,3}_avg          sensor_readings
    yankee_vibration_bearing_{1,2,3}_max          sensor_readings
    yankee_vibration_bearing_{1,2,3}_trend_7d     computed
    visconip_nip_pressure_avg                     sensor_readings
    aircap_inlet_temp_avg                         sensor_readings
    rewinder_speed_avg                            sensor_readings
    yankee_steam_pressure_avg                     sensor_readings
    days_since_last_maintenance_yankee            maintenance_logs
    days_since_last_maintenance_visconip          maintenance_logs
    hours_since_last_maintenance                  maintenance_logs
    avg_oee_percent                               production_runs
    target_failure_within_72h  (0/1)              sensor_failure_events

machine_id and component_id values are the lowercase-hyphenated IDs from
docs/API_CONTRACT-2.md so downstream layers (Prompt 3 AI, FastAPI
endpoints) can reference them directly without remapping.

Run:
    python backend/timescale/etl.py                       # prints summary
    python backend/timescale/etl.py --out features.parquet
    python backend/timescale/etl.py --start 2026-04-01 --end 2026-04-25
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


# Same defaults as the rest of the backend so a single DATABASE_URL works.
DEFAULT_DB_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/fhh"

# Baselines for "temperature_deviation_from_baseline" — the per-sensor mu
# the simulator uses. Kept in sync manually with sensor_simulator.SENSORS.
SENSOR_BASELINES = {
    "yankee_surface_temp":         110.0,
    "yankee_steam_pressure":       9.0,
    "yankee_vibration_bearing_1":  3.0,
    "yankee_vibration_bearing_2":  3.0,
    "yankee_vibration_bearing_3":  3.0,
    "visconip_nip_pressure":       5.0,
    "aircap_inlet_temp":           500.0,
    "rewinder_speed":              2050.0,
}

VIBRATION_SENSORS = [
    "yankee_vibration_bearing_1",
    "yankee_vibration_bearing_2",
    "yankee_vibration_bearing_3",
]

# Feature targets — used to fill missing days_since_* columns when a machine
# has no maintenance for the given component (extreme but possible).
LARGE_DAYS_SENTINEL = 9999


# =============================================================================
# Connections
# =============================================================================

def _get_engine(env_var: str = "DATABASE_URL") -> Engine:
    """Both the time-series and relational tables can live in the same Supabase
    database, so a single ``DATABASE_URL`` is the common case. Override per
    layer with ``TIMESCALE_DATABASE_URL`` / ``POSTGRES_DATABASE_URL`` if you
    ever split them onto separate servers."""
    url = os.environ.get(env_var) or os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    return create_engine(url, future=True, pool_pre_ping=True)


# =============================================================================
# Loaders
# =============================================================================

def load_hourly_sensor_aggregates(
    engine: Engine,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> pd.DataFrame:
    """Hourly avg / min / max / std per (machine_id, sensor_type) bucket."""
    where = []
    params: dict = {}
    if start is not None:
        where.append('"timestamp" >= :start')
        params["start"] = start
    if end is not None:
        where.append('"timestamp" < :end')
        params["end"] = end
    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    sql = text(f"""
        SELECT
            date_trunc('hour', "timestamp") AS hour_bucket,
            machine_id,
            sensor_type,
            AVG(value)::float8                              AS avg,
            MIN(value)::float8                              AS min,
            MAX(value)::float8                              AS max,
            COALESCE(STDDEV_POP(value), 0.0)::float8        AS std
        FROM sensor_readings
        {where_clause}
        GROUP BY hour_bucket, machine_id, sensor_type
        ORDER BY hour_bucket, machine_id, sensor_type
    """)
    return pd.read_sql(sql, engine, params=params)


def aggregate_hourly_in_memory(
    raw: pd.DataFrame,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> pd.DataFrame:
    """In-memory equivalent of ``load_hourly_sensor_aggregates``.

    Mirrors the SQL exactly: ``date_trunc('hour', timestamp)`` + GROUP BY +
    AVG/MIN/MAX/STDDEV_POP. Returns a DataFrame with the same columns
    (hour_bucket, machine_id, sensor_type, avg, min, max, std) so the rest
    of the ETL — pivot, feature engineering — runs unchanged.
    """
    if raw.empty:
        return pd.DataFrame(columns=["hour_bucket", "machine_id", "sensor_type",
                                     "avg", "min", "max", "std"])

    df = raw
    if start is not None:
        df = df[df["timestamp"] >= pd.Timestamp(start)]
    if end is not None:
        df = df[df["timestamp"] < pd.Timestamp(end)]

    df = df.assign(hour_bucket=df["timestamp"].dt.floor("1h"))
    agg = (
        df.groupby(["hour_bucket", "machine_id", "sensor_type"], as_index=False)["value"]
          .agg(
              avg="mean",
              min="min",
              max="max",
              # Match Postgres STDDEV_POP (population std, ddof=0).
              std=lambda v: float(v.std(ddof=0)) if len(v) else 0.0,
          )
          .sort_values(["hour_bucket", "machine_id", "sensor_type"])
          .reset_index(drop=True)
    )
    # STDDEV_POP returns 0 for single-row groups — make sure NaN doesn't slip through.
    agg["std"] = agg["std"].fillna(0.0)
    return agg


def load_production_runs(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(
        text("""
            SELECT run_id, machine_id, start_time, end_time,
                   product_grade, tons_produced, oee_percent, shift
            FROM production_runs
            ORDER BY machine_id, start_time
        """),
        engine,
        parse_dates=["start_time", "end_time"],
    )


def load_maintenance_logs(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(
        text("""
            SELECT log_id, machine_id, component_id, maintenance_type,
                   date_performed, cost_usd, downtime_hours
            FROM maintenance_logs
            ORDER BY machine_id, component_id, date_performed
        """),
        engine,
        parse_dates=["date_performed"],
    )


def load_failure_events(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(
        text("""
            SELECT event_id, machine_id, component_id, sensor_type,
                   degradation_start, failure_time, failure_mode
            FROM sensor_failure_events
            ORDER BY failure_time
        """),
        engine,
        parse_dates=["degradation_start", "failure_time"],
    )


# =============================================================================
# Feature engineering
# =============================================================================

def _pivot_hourly(agg: pd.DataFrame) -> pd.DataFrame:
    """Pivot hourly aggregates so each (machine_id, hour_bucket) is one row
    with columns ``<sensor_type>_avg``, ``<sensor_type>_max``, etc."""
    if agg.empty:
        return pd.DataFrame()

    wide = agg.pivot_table(
        index=["machine_id", "hour_bucket"],
        columns="sensor_type",
        values=["avg", "min", "max", "std"],
        aggfunc="first",
    )
    # Flatten MultiIndex columns: (avg, yankee_surface_temp) -> yankee_surface_temp_avg
    wide.columns = [f"{sensor}_{stat}" for stat, sensor in wide.columns]
    wide = wide.reset_index().sort_values(["machine_id", "hour_bucket"])
    return wide


def _add_temperature_deviation(df: pd.DataFrame) -> pd.DataFrame:
    """temperature_deviation_from_baseline = yankee_surface_temp_avg − baseline."""
    if "yankee_surface_temp_avg" in df.columns:
        df["temperature_deviation_from_baseline"] = (
            df["yankee_surface_temp_avg"] - SENSOR_BASELINES["yankee_surface_temp"]
        )
    return df


def _add_vibration_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Rolling 7-day slope (mm/s per day) of each bearing's hourly average,
    computed per-machine. Uses ``np.polyfit`` over a 168-hour window."""
    if df.empty:
        return df

    window = 24 * 7  # 168 hours = 7 days
    for sensor in VIBRATION_SENSORS:
        avg_col = f"{sensor}_avg"
        slope_col = f"{sensor}_trend_7d"
        if avg_col not in df.columns:
            df[slope_col] = np.nan
            continue

        slopes: list[float] = []
        # Independent rolling regression per machine — pandas .rolling().apply
        # with raw=True is fast enough at hourly resolution.
        def _slope(values: np.ndarray) -> float:
            n = len(values)
            if n < 2 or np.all(np.isnan(values)):
                return np.nan
            x = np.arange(n, dtype=float)
            mask = ~np.isnan(values)
            if mask.sum() < 2:
                return np.nan
            # Convert hourly index to days so the slope is per-day.
            slope, _ = np.polyfit(x[mask] / 24.0, values[mask], 1)
            return float(slope)

        df[slope_col] = (
            df.groupby("machine_id", group_keys=False)[avg_col]
              .apply(lambda s: s.rolling(window, min_periods=12).apply(_slope, raw=True))
              .values
        )
    return df


def _to_ns_utc(s: pd.Series) -> pd.Series:
    """Coerce a datetime series to ``datetime64[ns, UTC]``.

    pandas 2.x preserves the resolution of the input (so a date column ends
    up at second resolution, sensor timestamps at microsecond, etc.), and
    ``merge_asof`` refuses to join keys with mismatched resolutions. Forcing
    everything we merge on through this helper keeps the join keys
    compatible without changing any values.
    """
    return pd.to_datetime(s, utc=True).astype("datetime64[ns, UTC]")


def _add_days_since_maintenance(df: pd.DataFrame, logs: pd.DataFrame) -> pd.DataFrame:
    """For each (machine_id, hour_bucket), how many days have passed since
    the most recent maintenance log on:
      - any component (hours_since_last_maintenance, in hours)
      - the yankee   (days_since_last_maintenance_yankee)
      - the visconip (days_since_last_maintenance_visconip)
    """
    if df.empty:
        return df

    # Sort once for merge_asof; normalize the join key resolution.
    df = df.sort_values("hour_bucket").reset_index(drop=True).copy()
    df["hour_bucket"] = _to_ns_utc(df["hour_bucket"])
    out = df.copy()

    # --- any-component: hours since last maintenance event -----------------
    last_any = (
        logs[["machine_id", "date_performed"]]
        .rename(columns={"date_performed": "_last_any"})
        .copy()
    )
    last_any["_last_any"] = _to_ns_utc(last_any["_last_any"])
    last_any = last_any.sort_values(["machine_id", "_last_any"])
    out = pd.merge_asof(
        out.sort_values("hour_bucket"),
        last_any.sort_values("_last_any"),
        left_on="hour_bucket", right_on="_last_any", by="machine_id",
        direction="backward",
    )
    out["hours_since_last_maintenance"] = (
        (out["hour_bucket"] - out["_last_any"]).dt.total_seconds() / 3600.0
    ).fillna(LARGE_DAYS_SENTINEL * 24).astype(float)
    out = out.drop(columns=["_last_any"])

    # --- per-component: yankee, visconip ----------------------------------
    for component_id in ("yankee", "visconip"):
        comp = (
            logs[logs["component_id"] == component_id][["machine_id", "date_performed"]]
            .rename(columns={"date_performed": f"_last_{component_id}"})
            .copy()
        )
        comp[f"_last_{component_id}"] = _to_ns_utc(comp[f"_last_{component_id}"])
        comp = comp.sort_values(["machine_id", f"_last_{component_id}"])
        out = pd.merge_asof(
            out.sort_values("hour_bucket"),
            comp.sort_values(f"_last_{component_id}"),
            left_on="hour_bucket", right_on=f"_last_{component_id}", by="machine_id",
            direction="backward",
        )
        out[f"days_since_last_maintenance_{component_id}"] = (
            (out["hour_bucket"] - out[f"_last_{component_id}"]).dt.total_seconds() / 86_400.0
        ).fillna(LARGE_DAYS_SENTINEL).astype(float)
        out = out.drop(columns=[f"_last_{component_id}"])

    return out


def _add_oee(df: pd.DataFrame, runs: pd.DataFrame) -> pd.DataFrame:
    """Attach the OEE of the production_run that contains each hour_bucket."""
    if df.empty or runs.empty:
        df["avg_oee_percent"] = np.nan
        return df

    df = df.copy()
    df["hour_bucket"] = _to_ns_utc(df["hour_bucket"])

    runs = runs.copy()
    runs["start_time"] = _to_ns_utc(runs["start_time"])
    runs["end_time"] = _to_ns_utc(runs["end_time"])

    # Use merge_asof on start_time (backward) and then filter rows where the
    # bucket falls inside [start_time, end_time].
    out = pd.merge_asof(
        df.sort_values("hour_bucket"),
        runs[["machine_id", "start_time", "end_time", "oee_percent"]]
            .sort_values("start_time"),
        left_on="hour_bucket", right_on="start_time", by="machine_id",
        direction="backward",
    )
    inside_run = (out["hour_bucket"] >= out["start_time"]) & (out["hour_bucket"] < out["end_time"])
    out["avg_oee_percent"] = np.where(inside_run, out["oee_percent"], np.nan)
    return out.drop(columns=["start_time", "end_time", "oee_percent"])


def _add_failure_label(df: pd.DataFrame, events: pd.DataFrame, horizon_hours: int = 72) -> pd.DataFrame:
    """target_failure_within_72h = 1 if a failure_time for this machine_id
    falls in [hour_bucket, hour_bucket + horizon_hours]; else 0."""
    if df.empty:
        df["target_failure_within_72h"] = 0
        return df

    df["target_failure_within_72h"] = 0
    if events.empty:
        return df

    events = events.copy()
    events["failure_time"] = _to_ns_utc(events["failure_time"])
    df = df.copy()
    df["hour_bucket"] = _to_ns_utc(df["hour_bucket"])
    horizon = pd.Timedelta(hours=horizon_hours)
    for _, ev in events.iterrows():
        mask = (
            (df["machine_id"] == ev["machine_id"])
            & (df["hour_bucket"] >= ev["failure_time"] - horizon)
            & (df["hour_bucket"] <= ev["failure_time"])
        )
        df.loc[mask, "target_failure_within_72h"] = 1
    return df


# =============================================================================
# Top-level pipeline
# =============================================================================

@dataclass
class FeatureSet:
    df: pd.DataFrame
    n_rows: int
    n_features: int
    positive_rate: float


def build_feature_dataset(
    engine_ts: Optional[Engine] = None,
    engine_pg: Optional[Engine] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    in_memory: bool = False,
    interval_seconds: int = 300,
) -> FeatureSet:
    """Run the full ETL pipeline and return the ML-ready DataFrame plus stats.

    Two source modes:

    - ``in_memory=False`` (default): reads sensor_readings + sensor_failure_events
      from TimescaleDB, joins with production_runs + maintenance_logs in
      PostgreSQL.
    - ``in_memory=True``: skips TimescaleDB entirely. Calls
      ``sensor_simulator.simulate_to_dataframe`` to produce raw sensor data
      (and failure events) deterministically in-memory, aggregates to hourly
      buckets in pandas, then joins with production_runs + maintenance_logs
      from PostgreSQL just like the default path.
    """
    engine_pg = engine_pg or _get_engine("POSTGRES_DATABASE_URL")

    if in_memory:
        # Local import so etl can be inspected without dragging in the
        # simulator's deps when running the DB-only path in production.
        import sensor_simulator
        print("[etl]  --in-memory: generating sensor data via sensor_simulator")
        print(f"[etl]  interval={interval_seconds}s  "
              f"expected raw rows: {sensor_simulator.expected_row_count(interval_seconds):,}")
        raw, events = sensor_simulator.simulate_to_dataframe(
            interval_seconds=interval_seconds, seed=42,
        )
        print(f"[etl]  raw sensor frame: {len(raw):,} rows")
        agg = aggregate_hourly_in_memory(raw, start=start, end=end)
    else:
        engine_ts = engine_ts or _get_engine("TIMESCALE_DATABASE_URL")
        print("[etl]  loading hourly sensor aggregates from TimescaleDB ...")
        agg = load_hourly_sensor_aggregates(engine_ts, start=start, end=end)
        events = load_failure_events(engine_ts)

    print(f"[etl]  hourly aggregates: {len(agg):,} rows")

    print("[etl]  loading production_runs, maintenance_logs from PostgreSQL ...")
    runs = load_production_runs(engine_pg)
    logs = load_maintenance_logs(engine_pg)
    print(f"[etl]  runs={len(runs):,}  logs={len(logs):,}  events={len(events):,}")

    print("[etl]  pivoting + engineering features ...")
    df = _pivot_hourly(agg)
    df = _add_temperature_deviation(df)
    df = _add_vibration_trend(df)
    df = _add_days_since_maintenance(df, logs)
    df = _add_oee(df, runs)
    df = _add_failure_label(df, events, horizon_hours=72)

    feature_cols = [c for c in df.columns if c not in ("machine_id", "hour_bucket")]
    pos_rate = float(df["target_failure_within_72h"].mean()) if len(df) else 0.0

    print(f"[etl]  feature dataset: {len(df):,} rows × {len(feature_cols)} features")
    print(f"[etl]  positive rate (target_failure_within_72h=1): {pos_rate:.4%}")

    return FeatureSet(df=df, n_rows=len(df), n_features=len(feature_cols), positive_rate=pos_rate)


# =============================================================================
# CLI
# =============================================================================

def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    if "T" not in s:
        s = s + "T00:00:00"
    dt = datetime.fromisoformat(s.replace("Z", ""))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--start", type=str, default=None,
                   help="ISO date/datetime (UTC) — only aggregate readings >= this.")
    p.add_argument("--end", type=str, default=None,
                   help="ISO date/datetime (UTC) — only aggregate readings <  this.")
    p.add_argument("--out", type=str, default=None,
                   help="Optional output path — .parquet or .csv based on extension.")
    p.add_argument("--in-memory", action="store_true",
                   help="Skip TimescaleDB. Generate raw sensor data via "
                        "sensor_simulator.simulate_to_dataframe() and aggregate "
                        "in pandas. PostgreSQL (production_runs, maintenance_logs) "
                        "is still read from DATABASE_URL.")
    p.add_argument("--interval-seconds", type=int, default=300,
                   help="Sample interval in seconds for --in-memory mode "
                        "(default 300 = 5 min). Ignored without --in-memory.")
    args = p.parse_args()

    fs = build_feature_dataset(
        start=_parse_iso(args.start),
        end=_parse_iso(args.end),
        in_memory=args.in_memory,
        interval_seconds=args.interval_seconds,
    )

    print("\n[etl]  preview (head 3):")
    pd.set_option("display.max_columns", 80)
    pd.set_option("display.width", 200)
    print(fs.df.head(3).to_string())

    print("\n[etl]  feature columns:")
    for c in [c for c in fs.df.columns if c not in ("machine_id", "hour_bucket")]:
        print(f"  - {c}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.suffix.lower() == ".parquet":
            fs.df.to_parquet(out, index=False)
        else:
            fs.df.to_csv(out, index=False)
        print(f"\n[etl]  wrote {len(fs.df):,} rows → {out}")


if __name__ == "__main__":
    main()
