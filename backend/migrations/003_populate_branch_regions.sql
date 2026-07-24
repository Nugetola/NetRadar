-- ============================================================
-- MIGRATION: 003_populate_branch_regions.sql
-- DESCRIPTION: Populate region column for all 62 branches
-- PREREQUISITE: Migration 002 must be run first
-- ============================================================

-- ============================================================
-- 1. VERIFY COLUMN EXISTS
-- ============================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'branches' AND column_name = 'region'
    ) THEN
        RAISE EXCEPTION 'Column "region" does not exist! Run migration 002 first.';
    END IF;
END $$;

-- ============================================================
-- 2. POPULATE REGIONS
-- ============================================================

-- Addis Ababa (33 Branches)
UPDATE branches SET region = 'Addis Ababa' WHERE name IN (
    'Abdisa Aga Branch', 'Africa Godana Branch', 'Birbirsa Branch', 
    'Bole Branch', 'Bulbula Branch', 'Chaffe Branch', 'Chalchali Branch',
    'Doka Bora Branch', 'Dollo Biddena Branch', 'Ejersa Branch', 
    'Figa Branch', 'Finfinne Branch', 'Furi Branch', 'Gafarsa Branch',
    'General Tadesse Biru Branch', 'Gerji Branch',
    'Gofa Branch', 'Gofa Gebriel Branch', 'Gulele Branch',
    'Head Office Branch', 'Jamo Branch', 'Kality Branch', 'Kersa Branch',
    'Kolfe Branch', 'Kotobe Branch', 'Lebu Branch', 'Lemi Kura Branch',
    'Merkato Branch', 'Muda Branch', 'Saris Branch', 'Tullu Meti Branch',
    'Wadessa Branch'
);

-- Oromia (20 Branches)
UPDATE branches SET region = 'Oromia' WHERE name IN (
    'Adama Branch', 'Ambo Branch', 'Assela Branch', 'Bale Robe Branch',
    'Bishoftu Branch', 'Bule Hora Branch', 'Burayu Branch',
    'Dodola Branch', 'Gelan Branch',
    'Gimbi Branch', 'Holeta Branch', 'Jimma Branch',
    'Legatafo Branch', 'Meki Branch', 'Mettu Branch', 'Modjo Branch',
    'Nekemte Branch', 'Sebeta Branch', 'Selale Branch', 'Shashemene Branch',
    'Woliso Branch'
);

-- Amhara (2 Branches)
UPDATE branches SET region = 'Amhara' WHERE name IN (
    'Bahir Dar Branch', 'Dessie Branch'
);

-- Somali (1 Branch)
UPDATE branches SET region = 'Somali' WHERE name IN (
    'Jigjiga Branch'
);

-- SNNP (1 Branch)
UPDATE branches SET region = 'SNNP' WHERE name IN (
    'Hawassa Branch'
);

-- Benishangul-Gumuz (1 Branch)
UPDATE branches SET region = 'Benishangul-Gumuz' WHERE name IN (
    'Assosa Branch'
);

-- Gambela (1 Branch)
UPDATE branches SET region = 'Gambela' WHERE name IN (
    'Gambella Branch'
);

-- Harari (1 Branch)
UPDATE branches SET region = 'Harari' WHERE name IN (
    'Harar Branch'
);

-- Tigray (1 Branch)
UPDATE branches SET region = 'Tigray' WHERE name IN (
    'Mekele Branch'
);

-- ============================================================
-- 3. VERIFY
-- ============================================================
SELECT region, COUNT(*) as branch_count 
FROM branches 
GROUP BY region 
ORDER BY branch_count DESC;

-- ============================================================
-- 4. VERIFY NO NULLS REMAIN
-- ============================================================
DO $$ 
DECLARE
    null_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO null_count 
    FROM branches 
    WHERE region IS NULL;
    
    IF null_count > 0 THEN
        RAISE NOTICE 'âš ï¸ WARNING: % branches still have NULL region!', null_count;
        RAISE NOTICE 'Run: SELECT name FROM branches WHERE region IS NULL;';
    ELSE
        RAISE NOTICE 'âœ… All branches have region assigned!';
    END IF;
END $$;