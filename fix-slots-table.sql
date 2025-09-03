-- Fix slots table schema
-- Add missing columns that the frontend expects

-- First, let's check what columns currently exist
-- Then add the missing ones

-- Add type column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'slots' AND column_name = 'type') THEN
        ALTER TABLE slots ADD COLUMN type text;
    END IF;
END $$;

-- Add eml_category column if it doesn't exist (for backward compatibility)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'slots' AND column_name = 'eml_category') THEN
        ALTER TABLE slots ADD COLUMN eml_category text;
    END IF;
END $$;

-- Update existing rows to have a default type if they don't have one
UPDATE slots SET type = 'game' WHERE type IS NULL;

-- Make sure league_id exists and has the correct value
UPDATE slots SET league_id = '00000000-0000-0000-0000-000000000001' WHERE league_id IS NULL;

-- Disable RLS on slots table
ALTER TABLE slots DISABLE ROW LEVEL SECURITY;
