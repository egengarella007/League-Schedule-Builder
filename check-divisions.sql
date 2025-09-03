-- Check divisions in the database
SELECT id, name, created_at 
FROM divisions 
WHERE league_id = '00000000-0000-0000-0000-000000000001'
ORDER BY id;
