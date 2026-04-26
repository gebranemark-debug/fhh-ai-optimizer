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
maintenance_logs   ~120 rows  — preventive / corrective / predictive / emergency
alarm_events       ~600 rows  — info / warning / critical, ~8% unresolved
quality_scans   ~17,280 rows  — hourly basis-weight / moisture / softness / caliper
```

Total seeded volume: **20,189 rows** (well over the 10,000-row floor).

## Setup against Supabase (recommended)

### 1. Get your connection string

In the Supabase dashboard: **Project Settings → Database → Connection string → URI**.
It looks like:

```
postgresql://postgres:YOUR-PASSWORD@db.YOUR-PROJECT-REF.supabase.co:5432/postgres
```

### 2. Configure `DATABASE_URL` locally

Both `seed_data.py` and `db.py` read this env var; there is no hardcoded
fallback, so it must be set.

```bash
# from the repo root, copy the template (the real .env is gitignored)
cp .env.example .env
# edit .env and paste your Supabase URI in place of the placeholder

# load it into your current shell
export $(grep -v '^#' .env | xargs)

# verify
echo "$DATABASE_URL" | sed 's/:[^:@]*@/:***@/'   # masks the password
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

Pulls in `sqlalchemy` and `psycopg2-binary`. Supabase enforces SSL;
psycopg2 negotiates it automatically. If you ever hit SSL errors, append
`?sslmode=require` to the URL in `.env`.

### 4. Run the seed script against Supabase

```bash
python backend/postgres/seed_data.py
```

The script drops and recreates the 6 tables on the remote database, inserts
the canonical machines/components, generates 6 months of production runs,
maintenance, alarms, and quality scans, then prints a per-table count.
Expected final lines:

```
[seed] inserted:
  machines                 4
  components              24
  production_runs       2160
  maintenance_logs       121
  alarm_events           600
  quality_scans        17280
  TOTAL                20189
[seed] OK — exceeds 10,000-row target.
```

### 5. Verify the 20,189 rows landed

Two ways — pick one.

**Option A — run the smoke test (uses `db.py`):**
```bash
python backend/postgres/db.py
```
Prints the same per-table counts plus the `get_machine_status('al-nakheel')`
result.

**Option B — query directly with `psql`:**
```bash
psql "$DATABASE_URL" -c "
  SELECT 'machines' AS t, COUNT(*) FROM machines
  UNION ALL SELECT 'components',       COUNT(*) FROM components
  UNION ALL SELECT 'production_runs',  COUNT(*) FROM production_runs
  UNION ALL SELECT 'maintenance_logs', COUNT(*) FROM maintenance_logs
  UNION ALL SELECT 'alarm_events',     COUNT(*) FROM alarm_events
  UNION ALL SELECT 'quality_scans',    COUNT(*) FROM quality_scans;
"
```

Or one-liner total:
```bash
psql "$DATABASE_URL" -c "SELECT (
    (SELECT COUNT(*) FROM machines) +
    (SELECT COUNT(*) FROM components) +
    (SELECT COUNT(*) FROM production_runs) +
    (SELECT COUNT(*) FROM maintenance_logs) +
    (SELECT COUNT(*) FROM alarm_events) +
    (SELECT COUNT(*) FROM quality_scans)
) AS total_rows;"
```

You should see `total_rows = 20189`.

The seed is deterministic (RNG seeded with `42`, demo "today" pinned at
`2026-04-25`), so re-running produces the same row counts and IDs.

## Setup against local Postgres (alternative)

If you want to develop offline:

```bash
# install + start postgres (macOS)
brew install postgresql@16 && brew services start postgresql@16

# create the database and point DATABASE_URL at it
createdb fhh
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/fhh"

# then run the same seed/verify commands as above
python backend/postgres/seed_data.py
python backend/postgres/db.py
```

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
