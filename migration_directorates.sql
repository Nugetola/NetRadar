-- ============================================================================
-- Migration: Add Head Office Directorate support to OIC NetRadar
-- ============================================================================
-- Run this against your live PostgreSQL database to bring it in sync with
-- the updated models.py. Safe to re-run (uses IF NOT EXISTS guards where
-- possible), but ALWAYS take a backup first:
--
--     pg_dump -U <user> -d <dbname> -F c -f netradar_backup_before_migration.dump
--
-- Run with:
--     psql "postgresql://<user>:<password>@<host>:<port>/<dbname>" -f migration_directorates.sql
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. Create head_office_directorates table (does not exist yet)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS head_office_directorates (
    id      VARCHAR(36) PRIMARY KEY,
    name    VARCHAR(150) NOT NULL UNIQUE,
    code    VARCHAR(10) UNIQUE
);

-- ----------------------------------------------------------------------------
-- 2. Add branches.code column (does not exist yet)
-- ----------------------------------------------------------------------------
ALTER TABLE branches
    ADD COLUMN IF NOT EXISTS code VARCHAR(10) UNIQUE;

-- ----------------------------------------------------------------------------
-- 3. Add directorate_id to devices + agents
-- ----------------------------------------------------------------------------
ALTER TABLE devices
    ADD COLUMN IF NOT EXISTS directorate_id VARCHAR(36)
        REFERENCES head_office_directorates(id);

ALTER TABLE agents
    ADD COLUMN IF NOT EXISTS directorate_id VARCHAR(36)
        REFERENCES head_office_directorates(id);

-- ----------------------------------------------------------------------------
-- 4. Sanity check BEFORE adding the CHECK constraint:
--    every existing device/agent must already have branch_id set,
--    otherwise the constraint below will fail to apply.
--    This will print any rows that would violate the new rule.
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    bad_devices INT;
    bad_agents  INT;
BEGIN
    SELECT COUNT(*) INTO bad_devices FROM devices
        WHERE branch_id IS NULL AND directorate_id IS NULL;
    SELECT COUNT(*) INTO bad_agents FROM agents
        WHERE branch_id IS NULL AND directorate_id IS NULL;

    IF bad_devices > 0 THEN
        RAISE NOTICE 'WARNING: % device(s) have neither branch_id nor directorate_id set. Fix these before the CHECK constraint can be added.', bad_devices;
    END IF;

    IF bad_agents > 0 THEN
        RAISE NOTICE 'WARNING: % agent(s) have neither branch_id nor directorate_id set. Fix these before the CHECK constraint can be added.', bad_agents;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 5. Add CHECK constraints (mutual exclusivity: branch XOR directorate)
--    NOTE: if step 4 reported warnings, this will fail — fix the data first,
--    then re-run just this section.
-- ----------------------------------------------------------------------------
ALTER TABLE devices
    ADD CONSTRAINT ck_device_single_org_unit
    CHECK (
        (branch_id IS NOT NULL AND directorate_id IS NULL) OR
        (branch_id IS NULL AND directorate_id IS NOT NULL)
    );

ALTER TABLE agents
    ADD CONSTRAINT ck_agent_single_org_unit
    CHECK (
        (branch_id IS NOT NULL AND directorate_id IS NULL) OR
        (branch_id IS NULL AND directorate_id IS NOT NULL)
    );

COMMIT;

-- ============================================================================
-- If step 5 failed due to bad rows, run this to find them, fix manually
-- (assign a branch_id or directorate_id), then re-run section 5 only:
--
--   SELECT id, hostname FROM devices WHERE branch_id IS NULL AND directorate_id IS NULL;
--   SELECT id, full_name FROM agents WHERE branch_id IS NULL AND directorate_id IS NULL;
-- ============================================================================
