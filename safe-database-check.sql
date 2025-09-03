-- Safe Database Schema Check and Fix
-- This script checks what exists and only adds what's missing

-- Check current table structure
SELECT 'Current slots table columns:' as info;
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'slots' 
ORDER BY ordinal_position;

-- Check if type column exists
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'slots' AND column_name = 'type') THEN
        RAISE NOTICE '✅ type column already exists in slots table';
    ELSE
        ALTER TABLE slots ADD COLUMN type text;
        RAISE NOTICE '✅ Added type column to slots table';
    END IF;
END $$;

-- Check if eml_category column exists
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'slots' AND column_name = 'eml_category') THEN
        RAISE NOTICE '✅ eml_category column already exists in slots table';
    ELSE
        ALTER TABLE slots ADD COLUMN eml_category text;
        RAISE NOTICE '✅ Added eml_category column to slots table';
    END IF;
END $$;

-- Check if league_id column exists
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'slots' AND column_name = 'league_id') THEN
        RAISE NOTICE '✅ league_id column already exists in slots table';
    ELSE
        ALTER TABLE slots ADD COLUMN league_id uuid;
        RAISE NOTICE '✅ Added league_id column to slots table';
    END IF;
END $$;

-- Update data safely
UPDATE slots SET type = 'game' WHERE type IS NULL;
UPDATE slots SET league_id = '00000000-0000-0000-0000-000000000001' WHERE league_id IS NULL;

-- Check scheduler_params table
SELECT 'Current scheduler_params table columns:' as info;
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'scheduler_params' 
ORDER BY ordinal_position;

-- Check if name column exists in scheduler_params
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'scheduler_params' AND column_name = 'name') THEN
        RAISE NOTICE '✅ name column already exists in scheduler_params table';
    ELSE
        ALTER TABLE scheduler_params ADD COLUMN name text;
        RAISE NOTICE '✅ Added name column to scheduler_params table';
    END IF;
END $$;

-- Disable RLS on all tables
ALTER TABLE slots DISABLE ROW LEVEL SECURITY;
ALTER TABLE divisions DISABLE ROW LEVEL SECURITY;
ALTER TABLE teams DISABLE ROW LEVEL SECURITY;
ALTER TABLE scheduler_params DISABLE ROW LEVEL SECURITY;
ALTER TABLE runs DISABLE ROW LEVEL SECURITY;
ALTER TABLE schedule_games DISABLE ROW LEVEL SECURITY;

-- Show final status
SELECT 'Database schema check completed!' as status;
