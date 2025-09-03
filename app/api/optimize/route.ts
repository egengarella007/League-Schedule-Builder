import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path from 'path'

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

    // Prepare data for Python script
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
      force_full_validation: force_full_validation !== false  // Force full validation mode
    }

    // Call Python optimization script
    const result = await runPythonOptimization(optimizationData)
    
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

async function runPythonOptimization(data: any): Promise<any> {
  return new Promise((resolve, reject) => {
    // Create a simple test script to run the optimization
    const testScript = `
import sys
import json
import os

# We're already in the scheduler_api directory, so just add current directory to path
sys.path.insert(0, os.getcwd())

try:
    from schedule_optimizer import optimize_from_dict
    
    # Parse input data
    data = json.loads('''${JSON.stringify(data)}''')
    
    # Debug: Print received parameters
    print("🔧 Python received params:", file=sys.stderr)
    print("  earlyStart:", data.get('earlyStart', 'NOT_FOUND'), file=sys.stderr)
    print("  midStart:", data.get('midStart', 'NOT_FOUND'), file=sys.stderr)
    print("  blockSize:", data.get('blockSize', 'NOT_FOUND'), file=sys.stderr)
    print("  target_week:", data.get('target_week', 'NOT_FOUND'), file=sys.stderr)
    
    # Run optimization
    result = optimize_from_dict(data['schedule'], None, data)
    
    # Print result as JSON
    print(json.dumps(result))
    
except Exception as e:
    import traceback
    print(json.dumps({"error": str(e), "traceback": traceback.format_exc()}))
    sys.exit(1)
`

    const pythonProcess = spawn('python3', ['-c', testScript], {
      cwd: path.join(process.cwd(), 'scheduler_api'),
      env: { ...process.env, PYTHONPATH: path.join(process.cwd(), 'scheduler_api') }
    })

    let stdout = ''
    let stderr = ''

    pythonProcess.stdout.on('data', (data) => {
      stdout += data.toString()
    })

    pythonProcess.stderr.on('data', (data) => {
      stderr += data.toString()
      console.log('🔧 Python stderr:', data.toString())
    })

    pythonProcess.on('close', (code) => {
      console.log('🔧 Python process closed with code:', code)
      console.log('🔧 Python stdout length:', stdout.length)
      console.log('🔧 Python stdout (first 500 chars):', stdout.substring(0, 500))
      console.log('🔧 Python stderr length:', stderr.length)
      console.log('🔧 Python stderr (first 500 chars):', stderr.substring(0, 500))
      
      if (code === 0) {
        try {
          const result = JSON.parse(stdout)
          if (result.error) {
            reject(new Error(result.error))
          } else {
            resolve(result)
          }
        } catch (parseError) {
          console.log('🔧 Parse error:', parseError)
          reject(new Error(`Failed to parse Python output: ${parseError.message}. Raw output: ${stdout.substring(0, 200)}`))
        }
      } else {
        console.log('🔧 Python failed with code:', code)
        console.log('🔧 Full stderr:', stderr)
        reject(new Error(`Python script failed with code ${code}. Stderr: ${stderr || 'No error output'}`))
      }
    })

    pythonProcess.on('error', (error) => {
      reject(new Error(`Failed to start Python process: ${error.message}`))
    })
  })
}
