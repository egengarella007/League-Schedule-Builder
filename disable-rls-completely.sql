-- Completely disable RLS on all scheduler tables
-- This will bypass all RLS policy issues
-- Run this in Supabase SQL Editor

-- Disable RLS on all scheduler tables
ALTER TABLE runs DISABLE ROW LEVEL SECURITY;
ALTER TABLE scheduler_params DISABLE ROW LEVEL SECURITY;
ALTER TABLE slots DISABLE ROW LEVEL SECURITY;
ALTER TABLE teams DISABLE ROW LEVEL SECURITY;
ALTER TABLE divisions DISABLE ROW LEVEL SECURITY;
ALTER TABLE leagues DISABLE ROW LEVEL SECURITY;

-- Verify RLS is disabled
SELECT 
    schemaname,
    tablename,
    rowsecurity
FROM pg_tables 
WHERE tablename IN ('runs', 'scheduler_params', 'slots', 'teams', 'divisions', 'leagues')
ORDER BY tablename;

-- Test insert to verify it works
INSERT INTO runs (league_id, status) 
VALUES ('00000000-0000-0000-0000-000000000001', 'test')
RETURNING id, league_id, status;

-- Clean up test
DELETE FROM runs WHERE league_id = '00000000-0000-0000-0000-000000000001' AND status = 'test';

-- Test scheduler_params insert
INSERT INTO scheduler_params (league_id, name, params) 
VALUES ('00000000-0000-0000-0000-000000000001', 'test', '{"test": "data"}'::jsonb)
RETURNING id, league_id, name;

-- Clean up test
DELETE FROM scheduler_params WHERE league_id = '00000000-0000-0000-0000-000000000001' AND name = 'test';

-- Show final status
SELECT 'RLS Disabled Successfully!' as status;
