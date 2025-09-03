const { createClient } = require('@supabase/supabase-js')
const fs = require('fs')

const supabaseUrl = 'https://zcoupiuradompbrsebdp.supabase.co'
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpjb3VwaXVyYWRvbXBicnNlYmRwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY2MzQ3OTMsImV4cCI6MjA3MjIxMDc5M30.OaveieA8KkcWyMZr-H-0xwO6A38zjpGaFIJp3okfZlI'

const supabase = createClient(supabaseUrl, supabaseKey)

async function setupDatabase() {
  try {
    console.log('Setting up database tables...')
    
    // Read the SQL file
    const sql = fs.readFileSync('supabase-setup.sql', 'utf8')
    
    // Execute the SQL
    const { error } = await supabase.rpc('exec_sql', { sql })
    
    if (error) {
      console.error('Error setting up database:', error)
      return
    }
    
    console.log('Database tables created successfully!')
  } catch (error) {
    console.error('Error:', error)
  }
}

setupDatabase()
