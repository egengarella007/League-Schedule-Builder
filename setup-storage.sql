-- Set up storage bucket for schedule files
-- Run this in Supabase SQL Editor

-- Create the schedules bucket
INSERT INTO storage.buckets (id, name, public)
VALUES ('schedules', 'schedules', true)
ON CONFLICT (id) DO NOTHING;

-- Create policy to allow public read access to schedules
CREATE POLICY "Public Access" ON storage.objects
FOR SELECT USING (bucket_id = 'schedules');

-- Create policy to allow authenticated users to upload schedules
CREATE POLICY "Authenticated users can upload schedules" ON storage.objects
FOR INSERT WITH CHECK (bucket_id = 'schedules' AND auth.role() = 'authenticated');

-- Create policy to allow authenticated users to update schedules
CREATE POLICY "Authenticated users can update schedules" ON storage.objects
FOR UPDATE USING (bucket_id = 'schedules' AND auth.role() = 'authenticated');

-- Create policy to allow authenticated users to delete schedules
CREATE POLICY "Authenticated users can delete schedules" ON storage.objects
FOR DELETE USING (bucket_id = 'schedules' AND auth.role() = 'authenticated');
