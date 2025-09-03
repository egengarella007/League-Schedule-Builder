-- Check current RLS status on all scheduler tables
-- Run this in Supabase SQL Editor

SELECT 
    schemaname,
    tablename,
    rowsecurity as "RLS Enabled"
FROM pg_tables 
WHERE tablename IN ('runs', 'scheduler_params', 'slots', 'teams', 'divisions', 'leagues')
ORDER BY tablename;

-- Also check if there are any policies
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
WHERE tablename IN ('runs', 'scheduler_params', 'slots', 'teams', 'divisions', 'leagues')
ORDER BY tablename, policyname;
