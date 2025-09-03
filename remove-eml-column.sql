-- Remove the eml_category column from the slots table
ALTER TABLE slots DROP COLUMN IF EXISTS eml_category;
