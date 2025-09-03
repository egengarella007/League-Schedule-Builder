import { createClient } from '@supabase/supabase-js'

let supabase: any = null

// Default league ID for development
export const DEFAULT_LEAGUE_ID = '00000000-0000-0000-0000-000000000001'

// Create a function to get the Supabase client
export const getSupabaseClient = () => {
  if (supabase) {
    return supabase
  }

  // Only create the client if we're in the browser and have the required environment variables
  if (typeof window !== 'undefined') {
    try {
      const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://zcoupiuradompbrsebdp.supabase.co'
      const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpjb3VwaXVyYWRvbXBicnNlYmRwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY2MzQ3OTMsImV4cCI6MjA3MjIxMDc5M30.OaveieA8KkcWyMZr-H-0xwO6A38zjpGaFIJp3okfZlI'

      console.log('🔧 Initializing Supabase client with URL:', supabaseUrl)

      if (supabaseUrl && supabaseAnonKey) {
        supabase = createClient(supabaseUrl, supabaseAnonKey, {
          auth: {
            autoRefreshToken: true,
            persistSession: true,
            detectSessionInUrl: true
          },
          db: {
            schema: 'public'
          },
          global: {
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json'
            }
          }
        })
        console.log('✅ Supabase client initialized successfully')
        return supabase
      } else {
        console.error('❌ Missing Supabase URL or API key')
        return null
      }
    } catch (error) {
      console.error('❌ Error initializing Supabase client:', error)
      return null
    }
  }

  return null
}

// Export the client for backward compatibility
export { supabase }
