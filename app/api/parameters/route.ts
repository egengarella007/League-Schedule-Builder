import { NextRequest, NextResponse } from 'next/server'
import { getLatestParamsAction } from '@/app/actions/parameters'

export async function GET(request: NextRequest) {
  try {
    const params = await getLatestParamsAction()
    
    if (!params) {
      return NextResponse.json(
        { success: false, error: 'No parameters found or service not configured' },
        { status: 404 }
      )
    }

    return NextResponse.json({
      success: true,
      data: params
    })
  } catch (error) {
    console.error('Error fetching parameters:', error)
    return NextResponse.json(
      { success: false, error: 'Failed to fetch parameters' },
      { status: 500 }
    )
  }
}
