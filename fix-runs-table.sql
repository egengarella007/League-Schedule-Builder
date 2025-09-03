-- Fix runs table - add missing params_id column
-- Run this in your Supabase SQL editor

-- Add params_id column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'runs' AND column_name = 'params_id') THEN
        ALTER TABLE runs ADD COLUMN params_id uuid REFERENCES scheduler_params(id);
        RAISE NOTICE 'Added params_id column to runs table';
    ELSE
        RAISE NOTICE 'params_id column already exists in runs table';
    END IF;
END $$;

-- Verify the table structure
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'runs' 
ORDER BY ordinal_position;
