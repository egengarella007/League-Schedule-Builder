-- Temporarily disable RLS to bypass policy issues
-- Run this in Supabase SQL Editor

-- Disable RLS on all scheduler tables
ALTER TABLE runs DISABLE ROW LEVEL SECURITY;
ALTER TABLE scheduler_params DISABLE ROW LEVEL SECURITY;
ALTER TABLE slots DISABLE ROW LEVEL SECURITY;
ALTER TABLE teams DISABLE ROW LEVEL SECURITY;
ALTER TABLE divisions DISABLE ROW LEVEL SECURITY;

-- Verify RLS is disabled
SELECT 
    schemaname,
    tablename,
    rowsecurity
FROM pg_tables 
WHERE tablename IN ('runs', 'scheduler_params', 'slots', 'teams', 'divisions')
ORDER BY tablename;

-- Test insert to verify it works
INSERT INTO runs (league_id, status) 
VALUES ('00000000-0000-0000-0000-000000000000', 'test')
RETURNING id, league_id, status;

-- Clean up test
DELETE FROM runs WHERE league_id = '00000000-0000-0000-0000-000000000000';
