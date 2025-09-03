-- Create the imported_data table
CREATE TABLE IF NOT EXISTS imported_data (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  file_name TEXT NOT NULL,
  total_rows INTEGER NOT NULL,
  headers JSONB,
  eml_thresholds JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create the slots table
CREATE TABLE IF NOT EXISTS slots (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  import_id UUID REFERENCES imported_data(id) ON DELETE CASCADE,
  type TEXT,
  event_start TEXT NOT NULL,
  event_end TEXT NOT NULL,
  resource TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_slots_import_id ON slots(import_id);
CREATE INDEX IF NOT EXISTS idx_slots_row_index ON slots(row_index);
CREATE INDEX IF NOT EXISTS idx_imported_data_created_at ON imported_data(created_at);

-- Enable Row Level Security (RLS) - you can disable this if you want
ALTER TABLE imported_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE slots ENABLE ROW LEVEL SECURITY;

-- Create policies to allow all operations (for development)
-- In production, you might want more restrictive policies
CREATE POLICY "Allow all operations on imported_data" ON imported_data
  FOR ALL USING (true);

CREATE POLICY "Allow all operations on slots" ON slots
  FOR ALL USING (true);
