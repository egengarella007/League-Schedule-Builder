-- Complete Database Schema Fix
-- This script fixes all the schema issues we've encountered

-- 1. Fix scheduler_params table
DROP TABLE IF EXISTS scheduler_params CASCADE;

CREATE TABLE scheduler_params (
  id uuid primary key default gen_random_uuid(),
  league_id uuid not null,
  name text,  -- Add the missing name column
  params jsonb not null,
  created_at timestamptz not null default now()
);

-- 2. Fix slots table - add missing columns
DO $$ 
BEGIN
    -- Add type column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'slots' AND column_name = 'type') THEN
        ALTER TABLE slots ADD COLUMN type text;
    END IF;
    
    -- Add eml_category column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'slots' AND column_name = 'eml_category') THEN
        ALTER TABLE slots ADD COLUMN eml_category text;
    END IF;
END $$;

-- Update existing slots data
UPDATE slots SET type = 'game' WHERE type IS NULL;
UPDATE slots SET league_id = '00000000-0000-0000-0000-000000000001' WHERE league_id IS NULL;

-- 3. Ensure all tables have league_id
DO $$ 
BEGIN
    -- Add league_id to divisions if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'divisions' AND column_name = 'league_id') THEN
        ALTER TABLE divisions ADD COLUMN league_id uuid;
        UPDATE divisions SET league_id = '00000000-0000-0000-0000-000000000001' WHERE league_id IS NULL;
        ALTER TABLE divisions ALTER COLUMN league_id SET NOT NULL;
    END IF;
    
    -- Add league_id to teams if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teams' AND column_name = 'league_id') THEN
        ALTER TABLE teams ADD COLUMN league_id uuid;
        UPDATE teams SET league_id = '00000000-0000-0000-0000-000000000001' WHERE league_id IS NULL;
        ALTER TABLE teams ALTER COLUMN league_id SET NOT NULL;
    END IF;
    
    -- Add league_id to slots if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'slots' AND column_name = 'league_id') THEN
        ALTER TABLE slots ADD COLUMN league_id uuid;
        UPDATE slots SET league_id = '00000000-0000-0000-0000-000000000001' WHERE league_id IS NULL;
        ALTER TABLE slots ALTER COLUMN league_id SET NOT NULL;
    END IF;
END $$;

-- 4. Disable RLS on all tables
ALTER TABLE slots DISABLE ROW LEVEL SECURITY;
ALTER TABLE divisions DISABLE ROW LEVEL SECURITY;
ALTER TABLE teams DISABLE ROW LEVEL SECURITY;
ALTER TABLE scheduler_params DISABLE ROW LEVEL SECURITY;
ALTER TABLE runs DISABLE ROW LEVEL SECURITY;
ALTER TABLE schedule_games DISABLE ROW LEVEL SECURITY;

-- 5. Insert a default league if it doesn't exist
INSERT INTO leagues (id, name, created_at) 
VALUES ('00000000-0000-0000-0000-000000000001', 'Default League', NOW())
ON CONFLICT (id) DO NOTHING;

-- 6. Show the current state
SELECT 'Database schema fix completed successfully!' as status;
