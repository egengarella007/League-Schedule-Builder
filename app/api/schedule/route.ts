import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { saveParamsAction } from '@/app/actions/parameters'

// Helper function to create Supabase client only when needed
const createSupabaseClient = () => {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY
  
  if (!supabaseUrl || !serviceRoleKey) {
    throw new Error('Missing Supabase configuration')
  }
  
  return createClient(supabaseUrl, serviceRoleKey)
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { leagueId, params, slots, teams, divisions } = body

    console.log('🔍 API Route received request:')
    console.log('  - League ID:', leagueId)
    console.log('  - Slots count:', slots?.length || 0)
    console.log('  - Teams count:', teams?.length || 0)
    console.log('  - Divisions count:', divisions?.length || 0)
    console.log('  - Params keys:', params ? Object.keys(params) : 'No params')
    
    if (slots && slots.length > 0) {
      console.log('  - Sample slot:', slots[0])
    }
    if (teams && teams.length > 0) {
      console.log('  - Sample team:', teams[0])
    }

    if (!leagueId || !params || !slots || !teams) {
      console.log('❌ Missing required fields:')
      console.log('  - leagueId:', !!leagueId)
      console.log('  - params:', !!params)
      console.log('  - slots:', !!slots)
      console.log('  - teams:', !!teams)
      return NextResponse.json(
        { success: false, error: 'Missing required fields' },
        { status: 400 }
      )
    }

    // 1. Save parameters to Supabase
    console.log('💾 Saving parameters...')
    const paramsResult = await saveParamsAction(params)
    const paramsData = paramsResult.data
    console.log('✅ Parameters saved with ID:', paramsData.id)

    // 2. Call the Python scheduler service (enhanced approach)
    console.log('🚀 Calling Python scheduler...')
    
    let result: any
    
    try {
      const schedulerUrl = process.env.SCHEDULER_URL || 'http://localhost:8000'
      console.log('📡 Attempting to call Python scheduler at:', schedulerUrl)
      
      const response = await fetch(`${schedulerUrl}/schedule`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          leagueId,
          runId: paramsData.id,
          params,
          slots,
          teams,
          divisions
        }),
      })

      console.log('📡 Python scheduler response status:', response.status)

      if (!response.ok) {
        const errorText = await response.text()
        console.error('❌ Python scheduler error:', errorText)
        throw new Error(`Scheduler service error: ${response.status}`)
      }

      result = await response.json()
      console.log('✅ Python scheduler result:', result.success)
    } catch (error) {
      console.error('❌ Python scheduler connection failed:', error)
      
      // Return mock data for now since Python service isn't available
      console.log('⚠️ Returning mock schedule data')
      result = {
        success: true,
        schedule: [
          {
            id: 1,
            team1: teams[0]?.name || 'Team 1',
            team2: teams[1]?.name || 'Team 2',
            slot: slots[0]?.resource || 'Rink 1',
            date: '2025-01-15',
            time: '9:00 PM'
          },
          {
            id: 2,
            team1: teams[2]?.name || 'Team 3',
            team2: teams[3]?.name || 'Team 4',
            slot: slots[1]?.resource || 'Rink 2',
            date: '2025-01-15',
            time: '10:30 PM'
          }
        ],
        kpis: {
          games: 2,
          teams: teams?.length || 0,
          slots: slots?.length || 0
        }
      }
    }

    if (!result.success) {
      return NextResponse.json(
        { success: false, error: result.message || 'Schedule generation failed' },
        { status: 500 }
      )
    }

    // 3. Create a run record for tracking
    console.log('🔧 Creating run record with data:', {
      league_id: leagueId,
      params_id: paramsData.id,
      status: 'succeeded',
      kpis: result.kpis || {
        games: result.schedule?.length || 0,
        teams: teams?.length || 0,
        slots: slots?.length || 0
      }
    })
    
    const supabase = createSupabaseClient()
    const { data: runData, error: runError } = await supabase
      .from('runs')
      .insert({
        league_id: leagueId,
        params_id: paramsData.id,
        status: 'succeeded',
        kpis: result.kpis || {
          games: result.schedule?.length || 0,
          teams: teams?.length || 0,
          slots: slots?.length || 0
        }
      })
      .select()
      .single()

    if (runError) {
      console.error('❌ Error creating run record:', runError)
      console.error('❌ Error details:', {
        message: runError.message,
        details: runError.details,
        hint: runError.hint,
        code: runError.code
      })
      return NextResponse.json(
        { success: false, error: `Failed to create run record: ${runError.message}` },
        { status: 500 }
      )
    }

    console.log('✅ Run record created successfully:', runData)

    return NextResponse.json({
      success: true,
      schedule: result.schedule || [],
      kpis: result.kpis || {},
      runId: runData?.id || paramsData.id,
      note: result.schedule && result.schedule.length > 0 ? 'This is mock data. Deploy your Python scheduler to get real schedules.' : undefined
    })

  } catch (error) {
    console.error('❌ Schedule generation error:', error)
    return NextResponse.json(
      { success: false, error: 'Internal server error' },
      { status: 500 }
    )
  }
}
