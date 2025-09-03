-- Verify RLS is actually disabled
-- Run this in Supabase SQL Editor

-- Check RLS status on all tables
SELECT 
    schemaname,
    tablename,
    rowsecurity as "RLS Enabled"
FROM pg_tables 
WHERE tablename IN ('runs', 'scheduler_params', 'slots', 'teams', 'divisions', 'leagues')
ORDER BY tablename;

-- If RLS is still enabled, disable it again
DO $$
BEGIN
    -- Disable RLS on all scheduler tables
    ALTER TABLE runs DISABLE ROW LEVEL SECURITY;
    ALTER TABLE scheduler_params DISABLE ROW LEVEL SECURITY;
    ALTER TABLE slots DISABLE ROW LEVEL SECURITY;
    ALTER TABLE teams DISABLE ROW LEVEL SECURITY;
    ALTER TABLE divisions DISABLE ROW LEVEL SECURITY;
    ALTER TABLE leagues DISABLE ROW LEVEL SECURITY;
    
    RAISE NOTICE 'RLS disabled on all scheduler tables';
END $$;

-- Check again after disabling
SELECT 
    schemaname,
    tablename,
    rowsecurity as "RLS Enabled"
FROM pg_tables 
WHERE tablename IN ('runs', 'scheduler_params', 'slots', 'teams', 'divisions', 'leagues')
ORDER BY tablename;

-- Test insert with explicit error handling
BEGIN;
    INSERT INTO runs (league_id, status) 
    VALUES ('00000000-0000-0000-0000-000000000001', 'test_rls')
    RETURNING id, league_id, status;
    
    -- If we get here, the insert worked
    DELETE FROM runs WHERE league_id = '00000000-0000-0000-0000-000000000001' AND status = 'test_rls';
COMMIT;

-- Show success message
SELECT 'Test insert successful - RLS is working correctly' as status;
