import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { schedule, blockSize, blockRecipe, earlyStart, midStart, earlyEnd, midEnd, defaultGameMinutes, weights, wGlobal, wRolling, wRepeat, wDispersion, wLateFairness, globalSlack, rollingSlack, maxPasses, dryRun, optimize_days_since, force_full_validation, minRestDays } = body

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

    // Prepare data for Python scheduler
    const optimizationData = {
      schedule: schedule.map((game: any) => ({
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
      force_full_validation: force_full_validation !== false,  // Force full validation mode
      minRestDays: minRestDays || 0  // Minimum rest days between games
    }

    // Call Cloud Run Python scheduler for optimization
    const result = await callPythonScheduler(optimizationData)
    
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

async function callPythonScheduler(data: any): Promise<any> {
  try {
    // Get the Cloud Run URL from environment variable
    // You'll need to set this in your Vercel environment variables
    const schedulerUrl = process.env.SCHEDULER_URL || 'https://league-schedule-builder-1068724512018.europe-west1.run.app'
    
    console.log('🔧 Calling Python scheduler at:', schedulerUrl)
    
    const response = await fetch(`${schedulerUrl}/optimize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data)
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Python scheduler responded with ${response.status}: ${errorText}`)
    }

    const result = await response.json()
    return result

  } catch (error) {
    console.error('❌ Failed to call Python scheduler:', error)
    
    // Return a fallback response if the scheduler is unavailable
    return {
      error: 'Python scheduler unavailable',
      message: 'Optimization service is currently unavailable. Please try again later.',
      fallback: true
    }
  }
}
