-- Clean up divisions and recreate them properly
-- This will ensure your division gets ID 1

-- First, delete all teams (since they reference divisions)
DELETE FROM teams WHERE league_id = '00000000-0000-0000-0000-000000000001';

-- Delete all divisions
DELETE FROM divisions WHERE league_id = '00000000-0000-0000-0000-000000000001';

-- Reset the sequence to start from 1
ALTER SEQUENCE divisions_id_seq RESTART WITH 1;

-- Now when you create a new division in the UI, it will get ID 1
