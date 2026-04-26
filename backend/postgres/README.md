# FHH PostgreSQL Layer

Relational database layer for the FHH AI Optimizer. Holds the structured
business objects — machines, components, production runs, maintenance logs,
alarm events, and quality scans — that every other layer references.

All IDs, enums, and field names match `docs/API_CONTRACT-2.md` v1.1 exactly.

## Files

| File | Purpose |
|---|---|
| `schema.sql` | Table definitions + the `current_machine_status` view. Drops and recreates everything when run. |
| `seed_data.py` | Populates 6 months of realistic FHH demo data. Re-runnable. |
| `db.py` | SQLAlchemy 2.0 ORM models, CRUD helpers, and the `get_machine_status()` view function. |

## Tables

```
machines             4 rows   — al-nakheel, al-bardi, al-sindian, al-snobar
components          24 rows   — 6 components per machine, in line order
production_runs  ~2,160 rows  — 3 shifts/day x 4 machines x 180 days
maintenance_logs   ~200 rows  — preventive / corrective / predictive / emergency
alarm_events       ~600 rows  — info / warning / critical, ~8% unresolved
quality_scans   ~17,280 rows  — hourly basis-weight / moisture / softness / caliper
```

Total seeded volume: ~20,000 rows (well over the 10,000-row floor).

## Setup

### 1. Install Postgres locally

Anything 13+ works. On macOS:
```bash
brew install postgresql@16
brew services start postgresql@16
```

On Debian/Ubuntu:
```bash
sudo apt-get install postgresql
sudo systemctl start postgresql
```

### 2. Create the database

```bash
createdb fhh
```

(Or via psql: `CREATE DATABASE fhh;`)

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

This pulls in `sqlalchemy` and `psycopg2-binary`.

### 4. Configure the connection

The scripts read `DATABASE_URL` from the environment. The default is:

```
postgresql+psycopg2://postgres:postgres@localhost:5432/fhh
```

Override if your local setup differs:
```bash
export DATABASE_URL="postgresql+psycopg2://USER:PASSWORD@HOST:PORT/fhh"
```

### 5. Apply schema + seed data

```bash
python backend/postgres/seed_data.py
```

The script:
1. Drops and recreates all tables from `schema.sql`.
2. Inserts the canonical 4 machines and 24 components.
3. Generates 6 months of production runs, maintenance, alarms, and quality scans.
4. Backfills `components.last_maintenance_date` and `hours_since_last_maintenance`
   from the maintenance log it just wrote.
5. Asserts the row count is ≥ 10,000 and aborts otherwise.

Reproducible — the script seeds Python's RNG with `42`, and the demo
"today" is anchored at `2026-04-25` to match the API contract's example
timestamps.

### 6. Smoke-test the access layer

```bash
python backend/postgres/db.py
```

Prints row counts and the `get_machine_status('al-nakheel')` result. The
returned dict has the exact keys the API contract's `Machine object` defines
(with `risk_score` / `risk_tier` left at neutral defaults — those get filled
in by the AI layer in Prompt 3).

## Notes for downstream layers

- **TimescaleDB (Prompt 2)** will reference `machines.machine_id` and
  `components.(machine_id, component_id)` as foreign keys for sensor
  readings. Both are stable lowercase-hyphenated strings.
- **AI layer (Prompt 3)** will read aggregated features from this DB joined
  with the time-series store; the `current_machine_status` view is the
  fastest path to per-machine summaries.
- The `qcs_softness_index` sensor type from the API contract logically
  attaches to the `yankee` component (softness is generated at the Yankee
  creping stage). This affects sensor-side wiring, not the table layout
  here — `components` stays canonical at 6 rows per machine.
