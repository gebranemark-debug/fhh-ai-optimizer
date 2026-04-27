# FHH TimescaleDB Layer

Sensor data layer + ETL pipeline that turns raw machine telemetry into an
ML-ready feature dataset.

Sits on top of the PostgreSQL layer from Prompt 1; both layers can live in
the same Supabase database (one `DATABASE_URL`).

## Files

| File | Purpose |
|---|---|
| `schema.sql` | Creates `sensor_readings` (hypertable when TimescaleDB is available, regular indexed table otherwise) + `sensor_failure_events` for ML labels. |
| `sensor_simulator.py` | Generates 6 months of realistic sensor data for the 4 FHH machines, with 3 labeled bearing failures. Inserts in 5,000-row batched commits. |
| `etl.py` | Builds the hourly feature dataset by joining sensor aggregates with `production_runs` + `maintenance_logs` from Prompt 1. Adds engineered features. |

## What gets stored

### `sensor_readings`

One row per `(timestamp, machine_id, sensor_type)`. Default sample
interval is **5 minutes**; override with `--interval-seconds 60` for
literal 1-minute density.

Schema columns (from the build guide):

```
timestamp        TIMESTAMPTZ
machine_id       TEXT      -- al-nakheel | al-bardi | al-sindian | al-snobar
sensor_type      TEXT      -- API contract sensor type ID
sensor_location  TEXT      -- component_id (e.g. "yankee", "visconip")
value            FLOAT8
unit             TEXT      -- "°C", "bar", "mm/s", "m/min"
```

8 sensor streams per machine × 4 machines = **32 streams**:

| sensor_type | component | unit | normal range |
|---|---|---|---|
| `yankee_surface_temp` | yankee | °C | 100–120 |
| `yankee_steam_pressure` | yankee | bar | 8–10 |
| `yankee_vibration_bearing_1` | yankee | mm/s | 2–4 |
| `yankee_vibration_bearing_2` | yankee | mm/s | 2–4 |
| `yankee_vibration_bearing_3` | yankee | mm/s | 2–4 |
| `visconip_nip_pressure` | visconip | bar | 4–6 |
| `aircap_inlet_temp` | aircap | °C | 480–520 |
| `rewinder_speed` | rewinder | m/min | 1800–2222 |

`qcs_softness_index` (also in the API contract) lives on the
`yankee` component physically but is sampled by Valmet IQ QCS, not the
DCS — it's stored in `quality_scans` (PostgreSQL) and is intentionally
NOT generated here.

### Row count math

```
samples_per_machine = (180 days × 86,400 sec) / interval_seconds
total_rows          = samples_per_machine × 4 machines × 8 sensors
```

| `--interval-seconds` | rows |
|---|---|
| 60   | ≈ 8,294,400 |
| 300 (default) | ≈ 1,658,880 |
| 600  | ≈ 829,440 |

Default 5-min ≈ 1.66M rows — in the order of magnitude the prompt asks
for, dense enough for the hourly ETL aggregates to be statistically
meaningful, sparse enough to load through Supabase's Session Pooler in a
few minutes.

### `sensor_failure_events`

Three labeled bearing-failure windows the ML model trains against:

| event | machine | sensor | mode |
|---|---|---|---|
| `fail-001-al-bardi-yankee_vibration_bearing_2`   | al-bardi   | bearing 2 | `bearing_fatigue` |
| `fail-002-al-sindian-yankee_vibration_bearing_3` | al-sindian | bearing 3 | `bearing_lubrication_loss` |
| `fail-003-al-nakheel-yankee_vibration_bearing_3` | al-nakheel | bearing 3 | `bearing_fatigue` |

Each event has an 18-day degradation window before its `failure_time`,
during which the corresponding bearing's vibration ramps from ~3.0 mm/s
toward ~7.6 mm/s. The ETL labels every hour inside the 72-hour window
that *precedes* a failure as `target_failure_within_72h = 1`.

## Two execution modes

| Mode | When to use | DB writes | Sensor data lives in |
|---|---|---|---|
| **Default (DB)** | Production-style integration. Sensor history is queryable from any client and the FastAPI layer can read it directly. | yes — to `sensor_readings` + `sensor_failure_events` | TimescaleDB (or plain Postgres if the extension isn't available) |
| **`--in-memory`** | Demo / development workflow. Use when DB inserts are too slow (Supabase Session Pooler caps INSERT throughput around a few hundred rows/sec, which makes 1.66M rows take hours). The relational layer (`production_runs`, `maintenance_logs`) is still read from Postgres. | none for sensor data; ETL still reads PG | a pandas DataFrame, kept only for the duration of the run |

Both modes produce **bit-for-bit identical** raw sensor data (same RNG
seed, same anchor date, same failure events) and feed the same feature
engineering, so the resulting `features.parquet` is the same.

### Quickstart — fast in-memory demo

```bash
git pull origin main
export DATABASE_URL='<your Supabase Session Pooler URL>'
pip install -r requirements.txt
python backend/timescale/etl.py --in-memory --out backend/timescale/features.parquet
```

This skips TimescaleDB entirely. The simulator runs in-process, the
hourly aggregation happens in pandas, the joins to `production_runs` /
`maintenance_logs` still go to Supabase, and a parquet file lands in
`backend/timescale/features.parquet`. Total runtime: 1–3 minutes on a
typical Codespace.

## Setup

### Prereqs

- Prompt 1 already loaded (4 machines, 24 components, etc. — referenced
  by foreign-keyed `machine_id` and `component_id` values).
- `DATABASE_URL` exported in your shell, pointing at the same Supabase
  database (Session Pooler URL recommended). The default mode reads AND
  writes; the `--in-memory` mode only reads (production_runs,
  maintenance_logs).
- `pip install -r requirements.txt` (sqlalchemy, psycopg2-binary, pandas,
  numpy, pyarrow — all already in the repo's requirements file).

### TimescaleDB note (Supabase)

Supabase removed the `timescaledb` extension from new projects in 2024.
`schema.sql` handles this transparently:

1. It tries `CREATE EXTENSION IF NOT EXISTS timescaledb`.
2. If that succeeds, `sensor_readings` becomes a hypertable with 1-day
   chunks.
3. If it fails (Supabase post-2024 / plain Postgres), the script logs a
   `NOTICE` and `sensor_readings` stays a regular partition-free table.
   The composite PK and the two indexes still cover every read pattern
   the simulator and ETL use, so you'll see no functional difference at
   this data scale.

If you previously applied `schema.sql` via Supabase's SQL Editor (because
the Session Pooler doesn't love multi-statement DDL), use `--skip-schema`
when running the simulator — same pattern as Prompt 1.

### 1. Apply the schema

Either run the simulator without `--skip-schema` (it applies `schema.sql`
automatically) or paste `schema.sql` into the Supabase SQL Editor and
then run with `--skip-schema`.

### 2. Generate + insert sensor data

```bash
python backend/timescale/sensor_simulator.py
# or, after applying schema via SQL Editor:
python backend/timescale/sensor_simulator.py --skip-schema
```

Expected tail of the output:

```
[sim]  inserted:
  sensor_failure_events          3
  sensor_readings        1,658,880
[sim]  OK.
```

5,000-row commits stream the load through the pooler in chunks; you'll
see a progress line every 5,000 rows. Total runtime over a typical
broadband connection: 5–15 minutes.

### 3. Verify the load

```bash
psql "$DATABASE_URL" -c "
  SELECT 'sensor_readings' AS t, COUNT(*) FROM sensor_readings
  UNION ALL SELECT 'sensor_failure_events', COUNT(*) FROM sensor_failure_events;
"
```

Or via SQLAlchemy:

```bash
python -c "
from sqlalchemy import create_engine, text
import os
e = create_engine(os.environ['DATABASE_URL'])
with e.connect() as c:
    for t in ('sensor_readings', 'sensor_failure_events'):
        n = c.execute(text(f'SELECT COUNT(*) FROM {t}')).scalar_one()
        print(f'{t:25s} {n}')
"
```

### 4. Run the ETL

#### Default mode (reads sensor data from TimescaleDB)

```bash
python backend/timescale/etl.py
```

Prints the feature shape, a 3-row preview, and the list of feature
columns. To save the dataset:

```bash
python backend/timescale/etl.py --out backend/timescale/features.parquet
# or CSV
python backend/timescale/etl.py --out features.csv
```

To run on a window:

```bash
python backend/timescale/etl.py --start 2026-04-01 --end 2026-04-25
```

#### `--in-memory` mode (skips TimescaleDB)

For demos / fast iteration, especially when Supabase pooler INSERT
throughput is the bottleneck:

```bash
python backend/timescale/etl.py --in-memory --out backend/timescale/features.parquet
```

What happens:
1. `sensor_simulator.simulate_to_dataframe()` generates the same
   deterministic 32-stream dataset (RNG seed `42`, anchor `2026-04-25`)
   directly into a pandas DataFrame — no DB connection.
2. Hourly aggregation runs in pandas via `aggregate_hourly_in_memory`,
   which mirrors the SQL (`date_trunc('hour', timestamp)` + AVG/MIN/MAX/
   STDDEV_POP) so the downstream feature engineering is bit-for-bit the
   same.
3. `production_runs`, `maintenance_logs` are still loaded from Supabase
   Postgres (this is fast — a few thousand rows).
4. The full feature pipeline (pivot, vibration trend, days-since-
   maintenance, failure label) runs identically.
5. `--out` writes the resulting `features.parquet`.

You can also set the simulator interval per run (default 5 min):

```bash
python backend/timescale/etl.py --in-memory --interval-seconds 60 --out features.parquet
```

The standalone simulator also has an `--in-memory` flag for inspecting
the raw frame without going through the ETL:

```bash
python backend/timescale/sensor_simulator.py --in-memory --out raw.parquet
# also writes raw_failure_events.parquet alongside it
```

The ETL output has one row per `(machine_id, hour_bucket)`. With 6
months × 24 hours × 4 machines that's ~17,280 feature rows — a
manageable size for ML training in Prompt 3.

### Feature columns produced

| Column | Source | Notes |
|---|---|---|
| `machine_id` | sensor_readings | one of the 4 contract IDs |
| `hour_bucket` | sensor_readings | `date_trunc('hour', timestamp)` |
| `<sensor>_avg / _min / _max / _std` | sensor_readings | for each of the 8 sensors |
| `temperature_deviation_from_baseline` | computed | `yankee_surface_temp_avg − 110.0` |
| `yankee_vibration_bearing_{1,2,3}_trend_7d` | computed | rolling 168-hour slope, mm/s/day |
| `hours_since_last_maintenance` | maintenance_logs | hours since *any* maintenance |
| `days_since_last_maintenance_yankee` | maintenance_logs | days since last Yankee log |
| `days_since_last_maintenance_visconip` | maintenance_logs | days since last ViscoNip log |
| `avg_oee_percent` | production_runs | OEE of the run that contains this hour |
| `target_failure_within_72h` | sensor_failure_events | binary label, 1 in the 72h before any failure_time |

## Notes for downstream layers (Prompt 3 — AI)

- All `machine_id`, `component_id`, and `sensor_type` values are the
  exact lowercase-hyphenated IDs from `docs/API_CONTRACT-2.md` v1.1, so
  the FastAPI layer can pass them straight through without remapping.
- `temperature_deviation_from_baseline` and the per-bearing
  `_trend_7d` columns are exactly the engineered features called out in
  `docs/fhh_database_architecture.pdf` "WHAT THE ML MODEL NEEDS AS
  INPUT".
- `target_failure_within_72h` is ready for either a binary classifier or
  a regressor that emits a probability — Prompt 3 will use the regressor
  output (a continuous probability, per the build guide).
