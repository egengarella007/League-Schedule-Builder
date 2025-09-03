import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { saveParamsAction } from '@/app/actions/parameters'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
)

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
    const schedulerUrl = process.env.SCHEDULER_URL || 'http://localhost:8000'
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
      return NextResponse.json(
        { success: false, error: `Scheduler service error: ${response.status}` },
        { status: 500 }
      )
    }

    const result = await response.json()
    console.log('✅ Python scheduler result:', result.success)

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
      runId: runData?.id || paramsData.id
    })

  } catch (error) {
    console.error('❌ Schedule generation error:', error)
    return NextResponse.json(
      { success: false, error: 'Internal server error' },
      { status: 500 }
    )
  }
}
