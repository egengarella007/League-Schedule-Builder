import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '../../../lib/db'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { fileName, excelData, emlThresholds, summary } = body

    // Create the imported data record
    const importedData = await prisma.importedData.create({
      data: {
        fileName,
        totalRows: excelData.length,
        startDate: summary.startDate,
        endDate: summary.endDate,
        earlyCount: summary.earlyCount,
        midCount: summary.midCount,
        lateCount: summary.lateCount,
        emlThresholds,
        slots: {
          create: excelData.map((row: any[], index: number) => ({
            type: row[0] || null,
            eventStart: row[1] || '',
            eventEnd: row[2] || '',
            resource: row[3] || '',
            emlCategory: row[4] || 'Unknown',
            rowIndex: index
          }))
        }
      },
      include: {
        slots: {
          orderBy: {
            rowIndex: 'asc'
          }
        }
      }
    })

    return NextResponse.json({ success: true, data: importedData })
  } catch (error) {
    console.error('Error saving import data:', error)
    return NextResponse.json(
      { success: false, error: 'Failed to save import data' },
      { status: 500 }
    )
  }
}

export async function GET() {
  try {
    // Get the most recent import
    const latestImport = await prisma.importedData.findFirst({
      orderBy: {
        uploadedAt: 'desc'
      },
      include: {
        slots: {
          orderBy: {
            rowIndex: 'asc'
          }
        }
      }
    })

    return NextResponse.json({ success: true, data: latestImport })
  } catch (error) {
    console.error('Error fetching import data:', error)
    return NextResponse.json(
      { success: false, error: 'Failed to fetch import data' },
      { status: 500 }
    )
  }
}
