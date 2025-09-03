-- Complete Schema Migration for League Scheduler
-- This script creates all tables and migrates existing data

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Step 1: Create all tables with proper structure
CREATE TABLE IF NOT EXISTS leagues (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS divisions (
  id BIGSERIAL PRIMARY KEY,
  league_id UUID NOT NULL,
  name TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS teams (
  id BIGSERIAL PRIMARY KEY,
  league_id UUID NOT NULL,
  division_id BIGINT,
  name TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS slots (
  id BIGSERIAL PRIMARY KEY,
  league_id UUID NOT NULL,
  type TEXT,
  event_start TIMESTAMPTZ NOT NULL,
  event_end TIMESTAMPTZ NOT NULL,
  resource TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scheduler_params (
  id BIGSERIAL PRIMARY KEY,
  league_id UUID NOT NULL,
  name TEXT DEFAULT 'default',
  params JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS runs (
  id BIGSERIAL PRIMARY KEY,
  league_id UUID NOT NULL,
  params_id BIGINT,
  status TEXT NOT NULL DEFAULT 'queued',
  result_url TEXT,
  kpis JSONB,
  logs JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  error TEXT
);

-- Step 2: Create default league and division
INSERT INTO leagues (id, name) VALUES 
  ('00000000-0000-0000-0000-000000000001', 'Default League')
ON CONFLICT (id) DO NOTHING;

INSERT INTO divisions (league_id, name) VALUES 
  ('00000000-0000-0000-0000-000000000001', 'Default Division')
ON CONFLICT DO NOTHING;

-- Step 3: Add foreign key constraints
ALTER TABLE divisions ADD CONSTRAINT fk_divisions_league_id 
  FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE CASCADE;

ALTER TABLE teams ADD CONSTRAINT fk_teams_league_id 
  FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE CASCADE;

ALTER TABLE teams ADD CONSTRAINT fk_teams_division_id 
  FOREIGN KEY (division_id) REFERENCES divisions(id) ON DELETE CASCADE;

ALTER TABLE slots ADD CONSTRAINT fk_slots_league_id 
  FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE CASCADE;

ALTER TABLE scheduler_params ADD CONSTRAINT fk_scheduler_params_league_id 
  FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE CASCADE;

ALTER TABLE runs ADD CONSTRAINT fk_runs_league_id 
  FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE CASCADE;

ALTER TABLE runs ADD CONSTRAINT fk_runs_params_id 
  FOREIGN KEY (params_id) REFERENCES scheduler_params(id) ON DELETE SET NULL;

-- Step 4: Migrate existing data (if any)
-- Update existing teams to have proper division_id
UPDATE teams 
SET division_id = (SELECT id FROM divisions WHERE league_id = '00000000-0000-0000-0000-000000000001' LIMIT 1)
WHERE division_id IS NULL;

-- Make division_id NOT NULL for teams
ALTER TABLE teams ALTER COLUMN division_id SET NOT NULL;

-- Step 5: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_slots_league_id ON slots(league_id);
CREATE INDEX IF NOT EXISTS idx_slots_event_start ON slots(event_start);
CREATE INDEX IF NOT EXISTS idx_divisions_league_id ON divisions(league_id);
CREATE INDEX IF NOT EXISTS idx_teams_league_id ON teams(league_id);
CREATE INDEX IF NOT EXISTS idx_teams_division_id ON teams(division_id);
CREATE INDEX IF NOT EXISTS idx_scheduler_params_league_id ON scheduler_params(league_id);
CREATE INDEX IF NOT EXISTS idx_runs_league_id ON runs(league_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);

-- Step 6: Enable Row Level Security (RLS)
ALTER TABLE leagues ENABLE ROW LEVEL SECURITY;
ALTER TABLE divisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduler_params ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;

-- Step 7: Create permissive policies (for development)
DROP POLICY IF EXISTS "Allow all operations on leagues" ON leagues;
DROP POLICY IF EXISTS "Allow all operations on divisions" ON divisions;
DROP POLICY IF EXISTS "Allow all operations on teams" ON teams;
DROP POLICY IF EXISTS "Allow all operations on slots" ON slots;
DROP POLICY IF EXISTS "Allow all operations on scheduler_params" ON scheduler_params;
DROP POLICY IF EXISTS "Allow all operations on runs" ON runs;

CREATE POLICY "Allow all operations on leagues" ON leagues FOR ALL USING (true);
CREATE POLICY "Allow all operations on divisions" ON divisions FOR ALL USING (true);
CREATE POLICY "Allow all operations on teams" ON teams FOR ALL USING (true);
CREATE POLICY "Allow all operations on slots" ON slots FOR ALL USING (true);
CREATE POLICY "Allow all operations on scheduler_params" ON scheduler_params FOR ALL USING (true);
CREATE POLICY "Allow all operations on runs" ON runs FOR ALL USING (true);

-- Migration complete! 
-- All existing data should be preserved and associated with the default league.
