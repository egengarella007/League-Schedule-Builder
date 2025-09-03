import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { schedule, blockSize, blockRecipe, earlyStart, midStart, earlyEnd, midEnd, defaultGameMinutes, weights, wGlobal, wRolling, wRepeat, wDispersion, wLateFairness, globalSlack, rollingSlack, maxPasses, dryRun, optimize_days_since, force_full_validation } = body

    console.log('🔧 Optimization request received:', {
      gamesCount: schedule?.length,
      blockSize,
      blockRecipe,
      earlyStart: earlyStart || earlyEnd,
      midStart: midStart || midEnd,
      target_week: body.target_week,
      optimize_days_since,
      force_full_validation,
      dryRun
    })

    if (!schedule || !Array.isArray(schedule) || schedule.length === 0) {
      return NextResponse.json({ error: 'Invalid schedule data' }, { status: 400 })
    }

    // Prepare data for Cloud Run optimization
    const optimizationData = {
      schedule: schedule.map(game => ({
        id: game.id,
        start: game.start,
        end: game.end,
        rink: game.rink,
        div: game.div,
        home: game.home,
        away: game.away
      })),
      blockSize: blockSize || 10,
      blockRecipe: blockRecipe || { a: 6, b: 4 },
      earlyStart: earlyStart || "10:01 PM",  // ✅ Use START times for EML classification
      midStart: midStart || "10:31 PM",      // ✅ Use START times for EML classification
      target_week: body.target_week,         // 🎯 Pass target_week for step-by-step optimization
      defaultGameMinutes: defaultGameMinutes || 80,
      weights: weights || { w_eml: 1.0, w_runs: 0.2, w_rest: 0.6 },
      wGlobal: wGlobal || 2.0,
      wRolling: wRolling || 1.2,
      wRepeat: wRepeat || 1.0,
      wDispersion: wDispersion || 0.6,
      wLateFairness: wLateFairness || 1.0,
      globalSlack: globalSlack || 1,
      rollingSlack: rollingSlack || 0,
      maxPasses: maxPasses || 3,
      dryRun: dryRun !== false,
      optimize_days_since: optimize_days_since !== false,  // Force days-since optimization
      force_full_validation: force_full_validation !== false  // Force full validation mode
    }

    // Call Cloud Run optimization service
    const result = await callCloudRunOptimization(optimizationData)
    
    console.log('✅ Optimization completed:', {
      swapsCount: result.swaps?.length || 0,
      scoreImprovements: result.score_after
    })

    return NextResponse.json(result)

  } catch (error) {
    console.error('❌ Optimization error:', error)
    return NextResponse.json(
      { error: 'Optimization failed', details: error.message },
      { status: 500 }
    )
  }
}

async function callCloudRunOptimization(data: any): Promise<any> {
  return new Promise(async (resolve, reject) => {
    try {
      // Get Cloud Run URL from environment or use a default
      const cloudRunUrl = process.env.SCHEDULER_URL || 'https://league-schedule-builder-[your-hash]-ew.a.run.app'
      
      console.log('🔧 Calling Cloud Run optimization service at:', cloudRunUrl)
      
      const response = await fetch(`${cloudRunUrl}/optimize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })

      if (!response.ok) {
        const errorText = await response.text()
        console.error('❌ Cloud Run optimization error:', errorText)
        reject(new Error(`Cloud Run service error: ${response.status} - ${errorText}`))
        return
      }

      const result = await response.json()
      console.log('✅ Cloud Run optimization successful')
      resolve(result)
      
    } catch (error) {
      console.error('❌ Cloud Run optimization connection failed:', error)
      reject(new Error(`Failed to connect to Cloud Run service: ${error.message}`))
    }
  })
}
