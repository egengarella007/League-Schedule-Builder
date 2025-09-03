-- Fix RLS policies for the scheduler tables
-- This script should be run in the Supabase SQL editor

-- 1. Enable RLS on tables if not already enabled
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduler_params ENABLE ROW LEVEL SECURITY;

-- 2. Drop existing policies if they exist (to avoid conflicts)
DROP POLICY IF EXISTS "Enable insert for authenticated users only" ON runs;
DROP POLICY IF EXISTS "Enable select for authenticated users only" ON runs;
DROP POLICY IF EXISTS "Enable update for authenticated users only" ON runs;
DROP POLICY IF EXISTS "Enable delete for authenticated users only" ON runs;

DROP POLICY IF EXISTS "Enable insert for authenticated users only" ON scheduler_params;
DROP POLICY IF EXISTS "Enable select for authenticated users only" ON scheduler_params;
DROP POLICY IF EXISTS "Enable update for authenticated users only" ON scheduler_params;
DROP POLICY IF EXISTS "Enable delete for authenticated users only" ON scheduler_params;

-- 3. Create policies for runs table
-- Allow insert for any user (since we're using anonymous access)
CREATE POLICY "Enable insert for all users" ON runs
    FOR INSERT WITH CHECK (true);

-- Allow select for any user
CREATE POLICY "Enable select for all users" ON runs
    FOR SELECT USING (true);

-- Allow update for any user
CREATE POLICY "Enable update for all users" ON runs
    FOR UPDATE USING (true);

-- Allow delete for any user
CREATE POLICY "Enable delete for all users" ON runs
    FOR DELETE USING (true);

-- 4. Create policies for scheduler_params table
-- Allow insert for any user
CREATE POLICY "Enable insert for all users" ON scheduler_params
    FOR INSERT WITH CHECK (true);

-- Allow select for any user
CREATE POLICY "Enable select for all users" ON scheduler_params
    FOR SELECT USING (true);

-- Allow update for any user
CREATE POLICY "Enable update for all users" ON scheduler_params
    FOR UPDATE USING (true);

-- Allow delete for any user
CREATE POLICY "Enable delete for all users" ON scheduler_params
    FOR DELETE USING (true);

-- 5. Also ensure other tables have proper policies
-- For slots table
DROP POLICY IF EXISTS "Enable insert for authenticated users only" ON slots;
DROP POLICY IF EXISTS "Enable select for authenticated users only" ON slots;
DROP POLICY IF EXISTS "Enable update for authenticated users only" ON slots;
DROP POLICY IF EXISTS "Enable delete for authenticated users only" ON slots;

CREATE POLICY "Enable insert for all users" ON slots
    FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable select for all users" ON slots
    FOR SELECT USING (true);
CREATE POLICY "Enable update for all users" ON slots
    FOR UPDATE USING (true);
CREATE POLICY "Enable delete for all users" ON slots
    FOR DELETE USING (true);

-- For teams table
DROP POLICY IF EXISTS "Enable insert for authenticated users only" ON teams;
DROP POLICY IF EXISTS "Enable select for authenticated users only" ON teams;
DROP POLICY IF EXISTS "Enable update for authenticated users only" ON teams;
DROP POLICY IF EXISTS "Enable delete for authenticated users only" ON teams;

CREATE POLICY "Enable insert for all users" ON teams
    FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable select for all users" ON teams
    FOR SELECT USING (true);
CREATE POLICY "Enable update for all users" ON teams
    FOR UPDATE USING (true);
CREATE POLICY "Enable delete for all users" ON teams
    FOR DELETE USING (true);

-- For divisions table
DROP POLICY IF EXISTS "Enable insert for authenticated users only" ON divisions;
DROP POLICY IF EXISTS "Enable select for authenticated users only" ON divisions;
DROP POLICY IF EXISTS "Enable update for authenticated users only" ON divisions;
DROP POLICY IF EXISTS "Enable delete for authenticated users only" ON divisions;

CREATE POLICY "Enable insert for all users" ON divisions
    FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable select for all users" ON divisions
    FOR SELECT USING (true);
CREATE POLICY "Enable update for all users" ON divisions
    FOR UPDATE USING (true);
CREATE POLICY "Enable delete for all users" ON divisions
    FOR DELETE USING (true);

-- 6. Verify the policies were created
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check 
FROM pg_policies 
WHERE tablename IN ('runs', 'scheduler_params', 'slots', 'teams', 'divisions')
ORDER BY tablename, policyname;
