import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path from 'path'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { schedule_data, late_threshold = '22:31' } = body

    if (!schedule_data) {
      return NextResponse.json(
        { error: 'Missing schedule_data parameter' },
        { status: 400 }
      )
    }

    console.log('🚀 Starting Days Since Last Played optimization...')
    console.log(`📊 Schedule data: ${schedule_data.buckets?.length || 0} buckets`)
    console.log(`⏰ Late threshold: ${late_threshold}`)

    // Prepare input for the Python script
    const input_data = {
      schedule_data,
      late_threshold
    }

    // Run the Python optimization script
    const script_path = path.join(process.cwd(), 'scheduler_api', 'days_since_optimizer.py')
    
    return new Promise<NextResponse>((resolve) => {
      const python_process = spawn('python3', [script_path], {
        stdio: ['pipe', 'pipe', 'pipe']
      })

      let stdout_data = ''
      let stderr_data = ''

      // Send input data to the Python script
      python_process.stdin.write(JSON.stringify(input_data))
      python_process.stdin.end()

      // Collect stdout (JSON response)
      python_process.stdout.on('data', (data) => {
        stdout_data += data.toString()
      })

      // Collect stderr (debug/logging output)
      python_process.stderr.on('data', (data) => {
        stderr_data += data.toString()
        console.log(`🐍 Python stderr: ${data.toString()}`)
      })

      // Handle process completion
      python_process.on('close', (code) => {
        console.log(`🐍 Python process exited with code ${code}`)
        
        if (code !== 0) {
          console.error('❌ Python script failed')
          console.error('Stderr output:', stderr_data)
          
          resolve(NextResponse.json(
            { 
              error: 'Days optimization failed', 
              details: `Python script failed with code ${code}. Stderr: ${stderr_data}` 
            },
            { status: 500 }
          ))
          return
        }

        try {
          // Parse the JSON response from Python
          const result = JSON.parse(stdout_data)
          
          if (!result.success) {
            console.error('❌ Python script returned error:', result.error)
            resolve(NextResponse.json(
              { 
                error: 'Days optimization failed', 
                details: result.error 
              },
              { status: 500 }
            ))
            return
          }

          console.log('✅ Days optimization completed successfully!')
          console.log(`📊 Total changes made: ${result.total_changes}`)
          
          resolve(NextResponse.json({
            success: true,
            message: 'Days optimization completed successfully',
            optimized_schedule: result.optimized_schedule,
            changes_made: result.changes_made,
            total_changes: result.total_changes
          }))

        } catch (parse_error) {
          console.error('❌ Failed to parse Python output:', parse_error)
          console.error('Raw stdout:', stdout_data)
          
          resolve(NextResponse.json(
            { 
              error: 'Days optimization failed', 
              details: `Failed to parse Python output: ${parse_error}. Raw output: ${stdout_data}` 
            },
            { status: 500 }
          ))
        }
      })

      // Handle process errors
      python_process.on('error', (error) => {
        console.error('❌ Failed to start Python process:', error)
        resolve(NextResponse.json(
          { 
            error: 'Days optimization failed', 
            details: `Failed to start Python process: ${error.message}` 
          },
          { status: 500 }
        ))
      })

      // Set a timeout to prevent hanging
      setTimeout(() => {
        python_process.kill()
        resolve(NextResponse.json(
          { 
            error: 'Days optimization failed', 
            details: 'Process timed out after 60 seconds' 
          },
          { status: 500 }
        ))
      }, 60000) // 60 second timeout

    })

  } catch (error) {
    console.error('❌ Error in days optimization API:', error)
    return NextResponse.json(
      { 
        error: 'Days optimization failed', 
        details: error instanceof Error ? error.message : 'Unknown error' 
      },
      { status: 500 }
    )
  }
}
