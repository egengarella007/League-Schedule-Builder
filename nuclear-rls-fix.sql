-- Nuclear option: Completely remove all RLS policies and disable RLS
-- Run this in Supabase SQL Editor

-- First, drop ALL policies on scheduler tables
DO $$
DECLARE
    policy_record RECORD;
BEGIN
    FOR policy_record IN 
        SELECT schemaname, tablename, policyname 
        FROM pg_policies 
        WHERE tablename IN ('runs', 'scheduler_params', 'slots', 'teams', 'divisions', 'leagues')
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I.%I', 
                      policy_record.policyname, 
                      policy_record.schemaname, 
                      policy_record.tablename);
        RAISE NOTICE 'Dropped policy % on %.%', policy_record.policyname, policy_record.schemaname, policy_record.tablename;
    END LOOP;
END $$;

-- Disable RLS on all tables
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
    rowsecurity as "RLS Enabled"
FROM pg_tables 
WHERE tablename IN ('runs', 'scheduler_params', 'slots', 'teams', 'divisions', 'leagues')
ORDER BY tablename;

-- Verify no policies exist
SELECT COUNT(*) as "Remaining Policies" 
FROM pg_policies 
WHERE tablename IN ('runs', 'scheduler_params', 'slots', 'teams', 'divisions', 'leagues');

-- Test inserts
BEGIN;
    INSERT INTO scheduler_params (league_id, name, params) 
    VALUES ('00000000-0000-0000-0000-000000000001', 'test', '{"test": "data"}'::jsonb)
    RETURNING id, league_id, name;
    
    INSERT INTO runs (league_id, status) 
    VALUES ('00000000-0000-0000-0000-000000000001', 'test')
    RETURNING id, league_id, status;
    
    -- Clean up
    DELETE FROM scheduler_params WHERE league_id = '00000000-0000-0000-0000-000000000001' AND name = 'test';
    DELETE FROM runs WHERE league_id = '00000000-0000-0000-0000-000000000001' AND status = 'test';
COMMIT;

SELECT 'Nuclear RLS fix completed successfully!' as status;
