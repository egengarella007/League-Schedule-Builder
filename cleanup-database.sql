-- Remove any triggers that might reference eml_category
DROP TRIGGER IF EXISTS trigger_update_eml_category ON slots;

-- Remove any functions that might reference eml_category
DROP FUNCTION IF EXISTS calculate_eml_category(TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS update_eml_categories();
DROP FUNCTION IF EXISTS recalculate_all_eml_categories();

-- Remove the eml_category column from the slots table
ALTER TABLE slots DROP COLUMN IF EXISTS eml_category;
