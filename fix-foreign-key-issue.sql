-- Fix foreign key constraint issue
-- Run this in Supabase SQL Editor

-- 1. First, let's see what leagues exist
SELECT * FROM leagues;

-- 2. Create the default league with the correct ID (matches DEFAULT_LEAGUE_ID in code)
INSERT INTO leagues (id, name) 
VALUES ('00000000-0000-0000-0000-000000000001', 'Default League')
ON CONFLICT (id) DO NOTHING;

-- 3. Now test the insert with the correct league_id
INSERT INTO runs (league_id, status) 
VALUES ('00000000-0000-0000-0000-000000000001', 'test')
RETURNING id, league_id, status;

-- 4. Clean up test
DELETE FROM runs WHERE league_id = '00000000-0000-0000-0000-000000000001';

-- 5. Also test scheduler_params insert
INSERT INTO scheduler_params (league_id, name, params) 
VALUES ('00000000-0000-0000-0000-000000000001', 'test', '{"test": "data"}'::jsonb)
RETURNING id, league_id, name;

-- 6. Clean up test
DELETE FROM scheduler_params WHERE league_id = '00000000-0000-0000-0000-000000000001';

-- 7. Verify the foreign key constraints
SELECT 
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM 
    information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' 
    AND tc.table_name IN ('runs', 'scheduler_params', 'slots', 'teams', 'divisions');
