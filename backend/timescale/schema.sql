-- FHH AI Optimizer — TimescaleDB sensor layer
-- Source of truth for IDs/units: docs/API_CONTRACT-2.md v1.1.
--
-- Two tables:
--   sensor_readings        — high-frequency time series (5-min intervals).
--   sensor_failure_events  — 3 labeled failure windows for ML training.
--
-- TimescaleDB note: Supabase removed the `timescaledb` extension from new
-- projects in 2024. The DO block below tries to enable it and convert
-- sensor_readings into a hypertable, but degrades gracefully — if the
-- extension isn't available, the table stays a regular Postgres table with
-- the same indexes and the simulator/ETL keep working.

BEGIN;

DROP TABLE IF EXISTS sensor_readings        CASCADE;
DROP TABLE IF EXISTS sensor_failure_events  CASCADE;

-- =========================================================================
-- sensor_readings
-- Schema as specified in fhh_backend_build_guide.pdf Prompt 2:
--   timestamp, machine_id, sensor_type, sensor_location, value, unit
-- machine_id values are constrained to the 4 IDs in the API contract.
-- sensor_type is the 14-stream catalog from the contract; values used here:
--   yankee_surface_temp, yankee_steam_pressure,
--   yankee_vibration_bearing_1/2/3,
--   visconip_nip_pressure, aircap_inlet_temp, rewinder_speed.
-- sensor_location maps to a component_id (from PostgreSQL components table).
-- =========================================================================
CREATE TABLE sensor_readings (
    timestamp        TIMESTAMPTZ NOT NULL,
    machine_id       TEXT        NOT NULL
        CHECK (machine_id IN ('al-nakheel','al-bardi','al-sindian','al-snobar')),
    sensor_type      TEXT        NOT NULL,
    sensor_location  TEXT        NOT NULL,
    value            DOUBLE PRECISION NOT NULL,
    unit             TEXT        NOT NULL
);

-- Composite PK enforces uniqueness per (machine, sensor, timestamp). Including
-- timestamp lets TimescaleDB's hypertable partition on it.
ALTER TABLE sensor_readings
    ADD CONSTRAINT sensor_readings_pkey
    PRIMARY KEY (machine_id, sensor_type, "timestamp");

CREATE INDEX idx_sensor_readings_machine_sensor_ts
    ON sensor_readings (machine_id, sensor_type, "timestamp" DESC);
CREATE INDEX idx_sensor_readings_ts
    ON sensor_readings ("timestamp" DESC);

-- =========================================================================
-- sensor_failure_events
-- Three labeled bearing-failure windows the ML model learns from. Each row
-- represents one degradation-to-failure episode (vibration ramp + final
-- failure timestamp).
-- =========================================================================
CREATE TABLE sensor_failure_events (
    event_id         TEXT        PRIMARY KEY,
    machine_id       TEXT        NOT NULL
        CHECK (machine_id IN ('al-nakheel','al-bardi','al-sindian','al-snobar')),
    component_id     TEXT        NOT NULL
        CHECK (component_id IN ('headbox','visconip','yankee','aircap','softreel','rewinder')),
    sensor_type      TEXT        NOT NULL,
    degradation_start TIMESTAMPTZ NOT NULL,
    failure_time     TIMESTAMPTZ NOT NULL,
    failure_mode     TEXT        NOT NULL,
    description      TEXT
);
CREATE INDEX idx_failure_events_machine_time
    ON sensor_failure_events (machine_id, failure_time DESC);

COMMIT;

-- =========================================================================
-- TimescaleDB upgrade (best-effort).
-- If the timescaledb extension is installable, convert sensor_readings into
-- a hypertable with 1-day chunks. If not (Supabase post-2024, plain Postgres,
-- etc.), this whole block raises a NOTICE and the table stays as-is — the
-- indexes above are still effective for the read patterns we use.
-- =========================================================================
DO $$
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'timescaledb extension unavailable: %. sensor_readings will run as a regular partition-free table.', SQLERRM;
        RETURN;
    END;

    BEGIN
        PERFORM create_hypertable(
            'sensor_readings',
            'timestamp',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE,
            migrate_data => TRUE
        );
        RAISE NOTICE 'sensor_readings is now a TimescaleDB hypertable (1-day chunks).';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'create_hypertable failed: %. Continuing with a regular table.', SQLERRM;
    END;
END $$;
