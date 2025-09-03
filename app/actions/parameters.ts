'use server'

import { createClient } from '@supabase/supabase-js'
import { DEFAULT_LEAGUE_ID } from '@/lib/supabase'
import { SchedulerParamsData } from '@/lib/types'

const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://zcoupiuradompbrsebdp.supabase.co'

if (!serviceRoleKey) {
  throw new Error('SUPABASE_SERVICE_ROLE_KEY is not configured')
}

const supabase = createClient(
  supabaseUrl,
  serviceRoleKey
)

export async function saveParamsAction(params: SchedulerParamsData) {
  try {
    console.log('🔧 Attempting to save parameters with service role...')
    console.log('🔧 League ID:', DEFAULT_LEAGUE_ID)
    console.log('🔧 Parsed params:', JSON.stringify(params, null, 2))

    const { data, error } = await supabase
      .from('scheduler_params')
      .insert({
        league_id: DEFAULT_LEAGUE_ID,
        name: 'Latest Parameters', // Add the missing name field
        params: params
      })
      .select()
      .single()

    if (error) {
      console.error('❌ Service role insert failed:', error)
      throw new Error(`Failed to save parameters: ${error.message}`)
    }

    console.log('✅ Parameters saved successfully with service role')
    return { success: true, data }
  } catch (error) {
    console.error('❌ Error saving parameters:', error)
    throw error
  }
}

export async function getLatestParamsAction() {
  try {
    const { data, error } = await supabase
      .from('scheduler_params')
      .select('*')
      .eq('league_id', DEFAULT_LEAGUE_ID)
      .order('created_at', { ascending: false })
      .limit(1)
      .single()

    if (error) {
      console.error('Error fetching latest parameters:', error)
      return null
    }

    return data?.params || null
  } catch (error) {
    console.error('Error in getLatestParamsAction:', error)
    return null
  }
}
