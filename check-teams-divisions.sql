-- Check if teams and divisions exist in the database
-- Run this in Supabase SQL Editor

-- 1. Check if the default league exists
SELECT 'Leagues' as table_name, COUNT(*) as count FROM leagues;

-- 2. Check divisions
SELECT 'Divisions' as table_name, COUNT(*) as count FROM divisions WHERE league_id = '00000000-0000-0000-0000-000000000001';

-- 3. Check teams
SELECT 'Teams' as table_name, COUNT(*) as count FROM teams WHERE league_id = '00000000-0000-0000-0000-000000000001';

-- 4. Show actual data
SELECT 'Divisions Data:' as info;
SELECT id, name, league_id, created_at FROM divisions WHERE league_id = '00000000-0000-0000-0000-000000000001';

SELECT 'Teams Data:' as info;
SELECT id, name, division_id, league_id, created_at FROM teams WHERE league_id = '00000000-0000-0000-0000-000000000001';

-- 5. If no data exists, create some sample data
-- Create a sample division
INSERT INTO divisions (league_id, name) 
VALUES ('00000000-0000-0000-0000-000000000001', 'Sample Division')
ON CONFLICT DO NOTHING;

-- Get the division ID
SELECT id FROM divisions WHERE league_id = '00000000-0000-0000-0000-000000000001' LIMIT 1;

-- Create some sample teams (replace division_id with actual ID from above)
-- INSERT INTO teams (league_id, division_id, name) VALUES 
-- ('00000000-0000-0000-0000-000000000001', 1, 'Team 1'),
-- ('00000000-0000-0000-0000-000000000001', 1, 'Team 2'),
-- ('00000000-0000-0000-0000-000000000001', 1, 'Team 3');
