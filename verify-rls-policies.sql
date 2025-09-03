-- Verify RLS policies are active and working
-- Run this in Supabase SQL Editor

-- 1. Check if RLS is enabled on the tables
SELECT 
    schemaname,
    tablename,
    rowsecurity
FROM pg_tables 
WHERE tablename IN ('runs', 'scheduler_params', 'slots', 'teams', 'divisions')
ORDER BY tablename;

-- 2. Check all policies for these tables
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies 
WHERE tablename IN ('runs', 'scheduler_params', 'slots', 'teams', 'divisions')
ORDER BY tablename, policyname;

-- 3. Test insert permissions (this should work if policies are correct)
-- Try to insert a test row into runs table
INSERT INTO runs (league_id, status) 
VALUES ('00000000-0000-0000-0000-000000000000', 'queued')
RETURNING id, league_id, status;

-- 4. Clean up test row
DELETE FROM runs WHERE league_id = '00000000-0000-0000-0000-000000000000';
