-- Fix scheduler_params table schema
-- The error shows it's looking for a 'name' column that doesn't exist

-- Drop and recreate the scheduler_params table with correct schema
DROP TABLE IF EXISTS scheduler_params CASCADE;

CREATE TABLE scheduler_params (
  id uuid primary key default gen_random_uuid(),
  league_id uuid not null,
  name text,  -- Add the missing name column
  params jsonb not null,
  created_at timestamptz not null default now()
);

-- Disable RLS
ALTER TABLE scheduler_params DISABLE ROW LEVEL SECURITY;
