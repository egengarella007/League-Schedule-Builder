-- Proper League Scheduler Schema
-- This follows the row-by-row approach with proper data persistence

-- Input tables
create table if not exists slots (
  id uuid primary key default gen_random_uuid(),
  league_id uuid not null,
  event_start timestamptz not null,
  event_end   timestamptz not null,
  resource text,                -- rink
  unique(league_id, event_start, resource)
);

create table if not exists divisions (
  id uuid primary key default gen_random_uuid(),
  league_id uuid not null,
  name text not null
);

create table if not exists teams (
  id uuid primary key default gen_random_uuid(),
  league_id uuid not null,
  division_id uuid not null references divisions(id),
  name text not null
);

-- Parameters snapshots
create table if not exists scheduler_params (
  id uuid primary key default gen_random_uuid(),
  league_id uuid not null,
  params jsonb not null,
  created_at timestamptz not null default now()
);

-- Run + output
create table if not exists runs (
  id uuid primary key default gen_random_uuid(),
  league_id uuid not null,
  status text not null default 'running',   -- running|succeeded|failed
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  kpis jsonb
);

create table if not exists schedule_games (
  id bigserial primary key,
  league_id uuid not null,
  run_id uuid not null references runs(id),  -- Changed from bigint to uuid
  slot_id uuid not null references slots(id),
  division text,
  home_team text,
  away_team text,
  eml char(1),
  weekday text,
  note text
);

-- Add league_id to existing tables if they don't have it
DO $$ 
BEGIN
    -- Add league_id to slots if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'slots' AND column_name = 'league_id') THEN
        ALTER TABLE slots ADD COLUMN league_id uuid;
        UPDATE slots SET league_id = '00000000-0000-0000-0000-000000000001' WHERE league_id IS NULL;
        ALTER TABLE slots ALTER COLUMN league_id SET NOT NULL;
    END IF;
    
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
END $$;

-- Disable RLS for now (we'll use service role key)
ALTER TABLE slots DISABLE ROW LEVEL SECURITY;
ALTER TABLE divisions DISABLE ROW LEVEL SECURITY;
ALTER TABLE teams DISABLE ROW LEVEL SECURITY;
ALTER TABLE scheduler_params DISABLE ROW LEVEL SECURITY;
ALTER TABLE runs DISABLE ROW LEVEL SECURITY;
ALTER TABLE schedule_games DISABLE ROW LEVEL SECURITY;
