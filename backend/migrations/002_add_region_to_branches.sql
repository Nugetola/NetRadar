-- ============================================================
-- MIGRATION: 002_add_region_to_branches.sql
-- DESCRIPTION: Add region column to branches table
-- ============================================================

-- ============================================================
-- 1. ADD COLUMN
-- ============================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'branches' AND column_name = 'region'
    ) THEN
        ALTER TABLE branches ADD COLUMN region VARCHAR(100);
        RAISE NOTICE 'âœ… Added region column to branches table';
    ELSE
        RAISE NOTICE 'â„¹ï¸ region column already exists';
    END IF;
END $$;

-- ============================================================
-- 2. CREATE INDEX
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_branches_region ON branches(region);

-- ============================================================
-- 3. VERIFY
-- ============================================================
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'branches' 
AND column_name = 'region';