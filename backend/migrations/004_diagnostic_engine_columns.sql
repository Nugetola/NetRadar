-- ============================================================
-- MIGRATION: 004_diagnostic_engine_columns.sql
-- DESCRIPTION: Add diagnostic engine columns to devices table
-- ============================================================

-- ============================================================
-- 1. ADD switch_port_ifindex COLUMN
-- ============================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'devices' AND column_name = 'switch_port_ifindex'
    ) THEN
        ALTER TABLE devices ADD COLUMN switch_port_ifindex INT;
        RAISE NOTICE 'âœ… Added switch_port_ifindex column to devices table';
    ELSE
        RAISE NOTICE 'â„¹ï¸ switch_port_ifindex column already exists';
    END IF;
END $$;

-- ============================================================
-- 2. ADD is_dns_server COLUMN
-- ============================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'devices' AND column_name = 'is_dns_server'
    ) THEN
        ALTER TABLE devices ADD COLUMN is_dns_server BOOLEAN NOT NULL DEFAULT FALSE;
        RAISE NOTICE 'âœ… Added is_dns_server column to devices table';
    ELSE
        RAISE NOTICE 'â„¹ï¸ is_dns_server column already exists';
    END IF;
END $$;

-- ============================================================
-- 3. CREATE INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_devices_is_dns_server ON devices(is_dns_server);
CREATE INDEX IF NOT EXISTS idx_devices_switch_port_ifindex ON devices(switch_port_ifindex);

-- ============================================================
-- 4. VERIFY
-- ============================================================
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'devices' 
AND column_name IN ('switch_port_ifindex', 'is_dns_server')
ORDER BY column_name;