-- Fix teams table schema to match the expected structure
-- Run this in Supabase SQL Editor

-- Check if teams table exists and has the old schema
DO $$ 
BEGIN
    -- Check if teams table exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'teams') THEN
        -- Check if it's the old schema (has team_name column)
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'teams' AND column_name = 'team_name') THEN
            -- Rename team_name to name
            ALTER TABLE teams RENAME COLUMN team_name TO name;
            
            -- Check if division column exists and rename it
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name = 'teams' AND column_name = 'division') THEN
                -- Rename division to division_name temporarily
                ALTER TABLE teams RENAME COLUMN division TO division_name;
                
                -- Add new columns only if they don't exist
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name = 'teams' AND column_name = 'league_id') THEN
                    ALTER TABLE teams ADD COLUMN league_id UUID DEFAULT '00000000-0000-0000-0000-000000000001';
                END IF;
                
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name = 'teams' AND column_name = 'division_id') THEN
                    ALTER TABLE teams ADD COLUMN division_id BIGINT;
                END IF;
                
                -- Update division_id based on division_name
                UPDATE teams 
                SET division_id = (SELECT id FROM divisions WHERE name = teams.division_name LIMIT 1)
                WHERE division_id IS NULL;
                
                -- Drop the old division_name column
                ALTER TABLE teams DROP COLUMN division_name;
            END IF;
            
            -- Change id to BIGSERIAL if it's UUID
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name = 'teams' AND column_name = 'id' 
                       AND data_type = 'uuid') THEN
                -- Create a new sequence
                CREATE SEQUENCE IF NOT EXISTS teams_id_seq;
                
                -- Add a temporary column
                ALTER TABLE teams ADD COLUMN new_id BIGSERIAL;
                
                -- Drop the old primary key constraint
                ALTER TABLE teams DROP CONSTRAINT teams_pkey;
                
                -- Drop the old id column
                ALTER TABLE teams DROP COLUMN id;
                
                -- Rename new_id to id
                ALTER TABLE teams RENAME COLUMN new_id TO id;
                
                -- Add primary key constraint
                ALTER TABLE teams ADD PRIMARY KEY (id);
            END IF;
            
        ELSE
            -- New schema already exists, just add missing columns
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                           WHERE table_name = 'teams' AND column_name = 'league_id') THEN
                ALTER TABLE teams ADD COLUMN league_id UUID DEFAULT '00000000-0000-0000-0000-000000000001';
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                           WHERE table_name = 'teams' AND column_name = 'division_id') THEN
                ALTER TABLE teams ADD COLUMN division_id BIGINT;
            END IF;
        END IF;
    ELSE
        -- Create teams table with new schema
        CREATE TABLE teams (
          id BIGSERIAL PRIMARY KEY,
          league_id UUID NOT NULL,
          division_id BIGINT NOT NULL,
          name TEXT NOT NULL,
          created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    END IF;
END $$;

-- Make sure required columns are NOT NULL (only if they exist)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'teams' AND column_name = 'league_id') THEN
        ALTER TABLE teams ALTER COLUMN league_id SET NOT NULL;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'teams' AND column_name = 'division_id') THEN
        ALTER TABLE teams ALTER COLUMN division_id SET NOT NULL;
    END IF;
END $$;

-- Update any NULL division_id values
UPDATE teams 
SET division_id = (SELECT id FROM divisions WHERE league_id = '00000000-0000-0000-0000-000000000001' LIMIT 1)
WHERE division_id IS NULL;

-- Add foreign key constraints if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE constraint_name = 'fk_teams_league_id') THEN
        ALTER TABLE teams ADD CONSTRAINT fk_teams_league_id 
          FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE CASCADE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE constraint_name = 'fk_teams_division_id') THEN
        ALTER TABLE teams ADD CONSTRAINT fk_teams_division_id 
          FOREIGN KEY (division_id) REFERENCES divisions(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_teams_league_id ON teams(league_id);
CREATE INDEX IF NOT EXISTS idx_teams_division_id ON teams(division_id);

-- Enable RLS and create policies
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all operations on teams" ON teams;
CREATE POLICY "Allow all operations on teams" ON teams FOR ALL USING (true);

-- Verify the table structure
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'teams' 
ORDER BY ordinal_position;
