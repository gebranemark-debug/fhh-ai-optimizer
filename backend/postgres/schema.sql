-- FHH AI Optimizer — PostgreSQL relational schema
-- Source of truth for shapes: docs/API_CONTRACT-2.md (v1.1)
-- IDs are lowercase-hyphenated; enums are lowercase strings.

BEGIN;

DROP TABLE IF EXISTS quality_scans      CASCADE;
DROP TABLE IF EXISTS alarm_events       CASCADE;
DROP TABLE IF EXISTS maintenance_logs   CASCADE;
DROP TABLE IF EXISTS production_runs    CASCADE;
DROP TABLE IF EXISTS components         CASCADE;
DROP TABLE IF EXISTS machines           CASCADE;

-- =========================================================================
-- machines
-- 4 rows total (al-nakheel, al-bardi, al-sindian, al-snobar).
-- Mirrors the "Machine object" in API_CONTRACT §Shared data shapes.
-- =========================================================================
CREATE TABLE machines (
    machine_id           TEXT PRIMARY KEY
        CHECK (machine_id IN ('al-nakheel','al-bardi','al-sindian','al-snobar')),
    name                 TEXT        NOT NULL,
    location             TEXT        NOT NULL,
    model                TEXT        NOT NULL DEFAULT 'Valmet Advantage DCT 200TS',
    installation_date    DATE        NOT NULL,
    status               TEXT        NOT NULL DEFAULT 'running'
        CHECK (status IN ('running','idle','maintenance','offline')),
    current_speed_mpm    INTEGER     NOT NULL DEFAULT 0,
    current_oee_percent  NUMERIC(5,2) NOT NULL DEFAULT 0
);

-- =========================================================================
-- components
-- 6 per machine, in line order:
-- headbox -> visconip -> yankee -> aircap -> softreel -> rewinder.
-- Composite PK so component_id values repeat across machines.
-- =========================================================================
CREATE TABLE components (
    machine_id                    TEXT NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    component_id                  TEXT NOT NULL
        CHECK (component_id IN ('headbox','visconip','yankee','aircap','softreel','rewinder')),
    name                          TEXT NOT NULL,
    is_critical                   BOOLEAN NOT NULL DEFAULT FALSE,
    expected_lifetime_hours       INTEGER NOT NULL,
    hours_since_last_maintenance  INTEGER NOT NULL DEFAULT 0,
    last_maintenance_date         DATE,
    PRIMARY KEY (machine_id, component_id)
);

-- =========================================================================
-- production_runs
-- Tracks each shift's production. 3 shifts/day x 4 machines x ~180 days.
-- product_grade values map to the product CSV (facial tissue, toilet paper,
-- kitchen towel, napkin).
-- =========================================================================
CREATE TABLE production_runs (
    run_id          TEXT PRIMARY KEY,
    machine_id      TEXT NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ NOT NULL,
    product_grade   TEXT NOT NULL,
    tons_produced   NUMERIC(8,2) NOT NULL,
    oee_percent     NUMERIC(5,2) NOT NULL,
    shift           TEXT NOT NULL CHECK (shift IN ('a','b','c'))
);
CREATE INDEX idx_production_runs_machine_time ON production_runs (machine_id, start_time DESC);

-- =========================================================================
-- maintenance_logs
-- maintenance_type matches the API contract enum:
-- preventive | corrective | predictive | emergency.
-- =========================================================================
CREATE TABLE maintenance_logs (
    log_id           TEXT PRIMARY KEY,
    machine_id       TEXT NOT NULL,
    component_id     TEXT NOT NULL,
    maintenance_type TEXT NOT NULL
        CHECK (maintenance_type IN ('preventive','corrective','predictive','emergency')),
    date_performed   DATE NOT NULL,
    cost_usd         NUMERIC(10,2) NOT NULL,
    downtime_hours   NUMERIC(6,2) NOT NULL DEFAULT 0,
    technician       TEXT NOT NULL,
    notes            TEXT,
    FOREIGN KEY (machine_id, component_id)
        REFERENCES components(machine_id, component_id) ON DELETE CASCADE
);
CREATE INDEX idx_maint_machine_component ON maintenance_logs (machine_id, component_id, date_performed DESC);

-- =========================================================================
-- alarm_events
-- Mirrors the alarm shape returned by GET /machines/{id}/alarms.
-- =========================================================================
CREATE TABLE alarm_events (
    alarm_id         TEXT PRIMARY KEY,
    machine_id       TEXT NOT NULL REFERENCES machines(machine_id) ON DELETE CASCADE,
    timestamp        TIMESTAMPTZ NOT NULL,
    severity         TEXT NOT NULL CHECK (severity IN ('info','warning','critical')),
    description      TEXT NOT NULL,
    resolved_at      TIMESTAMPTZ,
    downtime_minutes INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_alarms_machine_time ON alarm_events (machine_id, timestamp DESC);
CREATE INDEX idx_alarms_severity ON alarm_events (severity);

-- =========================================================================
-- quality_scans
-- One row per hour per active production run (Valmet IQ QCS rollup).
-- =========================================================================
CREATE TABLE quality_scans (
    scan_id           TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES production_runs(run_id) ON DELETE CASCADE,
    timestamp         TIMESTAMPTZ NOT NULL,
    basis_weight_gsm  NUMERIC(6,2) NOT NULL,
    moisture_percent  NUMERIC(5,2) NOT NULL,
    softness_index    NUMERIC(5,2) NOT NULL,
    caliper_microns   NUMERIC(6,2) NOT NULL
);
CREATE INDEX idx_quality_run_time ON quality_scans (run_id, timestamp);

-- =========================================================================
-- View: current_machine_status
-- One row per machine with the cached health summary the frontend needs.
-- Used by db.get_machine_status() and ultimately by GET /machines.
-- =========================================================================
CREATE OR REPLACE VIEW current_machine_status AS
SELECT
    m.machine_id,
    m.name,
    m.location,
    m.model,
    m.installation_date,
    m.status,
    m.current_speed_mpm,
    m.current_oee_percent,
    (
        SELECT COUNT(*) FROM alarm_events a
        WHERE a.machine_id = m.machine_id AND a.resolved_at IS NULL
    )                                                               AS active_alerts_count,
    (
        SELECT COUNT(*) FROM alarm_events a
        WHERE a.machine_id = m.machine_id
          AND a.resolved_at IS NULL
          AND a.severity = 'critical'
    )                                                               AS active_critical_count,
    (
        SELECT MAX(date_performed) FROM maintenance_logs ml
        WHERE ml.machine_id = m.machine_id
    )                                                               AS last_maintenance_date
FROM machines m;

COMMIT;
