-- ============================================================================
-- FHH AI Optimizer — App schema (Path C: new features only)
-- ----------------------------------------------------------------------------
-- Adds tables for:
--   1. Authentication + RBAC (app_users)
--   2. User-written maintenance entries (user_maintenance_entries)
--   3. Chat memory (chat_conversations + chat_messages)
--
-- Independent of the analytics schema (machines, components, production_runs,
-- maintenance_logs, alarm_events, quality_scans). machine_id/component_id are
-- stored as strings and validated at the application layer against parquet.
--
-- Apply via:
--   psql "$DATABASE_URL" -f backend/postgres/app_schema.sql
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ----------------------------------------------------------------------------
-- 1. Users + RBAC
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(50)  NOT NULL CHECK (role IN ('admin', 'operator')),
    full_name       VARCHAR(255),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users(email);

-- ----------------------------------------------------------------------------
-- 2. User-written maintenance entries
-- ----------------------------------------------------------------------------
-- Form fields: type, work done, cost, time (performed_at + duration),
-- technician, machine, component
CREATE TABLE IF NOT EXISTS user_maintenance_entries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES app_users(id) ON DELETE RESTRICT,

    -- Soft references (string IDs validated at app layer, not FK'd to analytics)
    machine_id          VARCHAR(100) NOT NULL,
    component_id        VARCHAR(100),

    -- Form fields
    maintenance_type    VARCHAR(50)  NOT NULL CHECK (maintenance_type IN
                            ('preventive', 'corrective', 'predictive', 'inspection')),
    work_description    TEXT         NOT NULL,
    cost_usd            NUMERIC(12,2) CHECK (cost_usd IS NULL OR cost_usd >= 0),
    duration_hours      NUMERIC(6,2) CHECK (duration_hours IS NULL OR duration_hours >= 0),
    technician_name     VARCHAR(255) NOT NULL,
    performed_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_maint_machine_id     ON user_maintenance_entries(machine_id);
CREATE INDEX IF NOT EXISTS idx_user_maint_user_id        ON user_maintenance_entries(user_id);
CREATE INDEX IF NOT EXISTS idx_user_maint_performed_at   ON user_maintenance_entries(performed_at DESC);

-- ----------------------------------------------------------------------------
-- 3. Chat memory
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    title           VARCHAR(255),  -- auto-generated from first user message, editable
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Compound index supports "last 10 conversations for user X, newest first"
CREATE INDEX IF NOT EXISTS idx_chat_conv_user_updated
    ON chat_conversations(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    role                VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content             TEXT NOT NULL,
    data_sources_used   JSONB,  -- e.g. ["kpis/overview", "machines"]
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_conv_created
    ON chat_messages(conversation_id, created_at);

-- ----------------------------------------------------------------------------
-- Trigger: keep chat_conversations.updated_at fresh when messages are inserted
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION touch_chat_conversation_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE chat_conversations
    SET    updated_at = NOW()
    WHERE  id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS chat_messages_touch_conversation ON chat_messages;
CREATE TRIGGER chat_messages_touch_conversation
AFTER INSERT ON chat_messages
FOR EACH ROW EXECUTE FUNCTION touch_chat_conversation_updated_at();

-- ----------------------------------------------------------------------------
-- Verification queries (run manually after apply)
-- ----------------------------------------------------------------------------
-- \dt app_users user_maintenance_entries chat_conversations chat_messages
-- SELECT COUNT(*) FROM app_users;
-- SELECT COUNT(*) FROM user_maintenance_entries;
-- SELECT COUNT(*) FROM chat_conversations;
-- SELECT COUNT(*) FROM chat_messages;
