import { NextRequest, NextResponse } from 'next/server'

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

    // Prepare input for the Cloud Run service
    const input_data = {
      schedule_data,
      late_threshold
    }

    // Call Cloud Run days optimization service
    const result = await callCloudRunDaysOptimization(input_data)
    
    return NextResponse.json(result)

  } catch (error) {
    console.error('❌ Days optimization error:', error)
    return NextResponse.json(
      { error: 'Days optimization failed', details: error.message },
      { status: 500 }
    )
  }
}

async function callCloudRunDaysOptimization(data: any): Promise<any> {
  return new Promise(async (resolve, reject) => {
    try {
      // Get Cloud Run URL from environment or use a default
      const cloudRunUrl = process.env.SCHEDULER_URL || 'https://league-schedule-builder-[your-hash]-ew.a.run.app'
      
      console.log('🚀 Calling Cloud Run days optimization service at:', cloudRunUrl)
      
      const response = await fetch(`${cloudRunUrl}/days-optimize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })

      if (!response.ok) {
        const errorText = await response.text()
        console.error('❌ Cloud Run days optimization error:', errorText)
        reject(new Error(`Cloud Run service error: ${response.status} - ${errorText}`))
        return
      }

      const result = await response.json()
      console.log('✅ Cloud Run days optimization successful')
      resolve(result)
      
    } catch (error) {
      console.error('❌ Cloud Run days optimization connection failed:', error)
      reject(new Error(`Failed to connect to Cloud Run service: ${error.message}`))
    }
  })
}
