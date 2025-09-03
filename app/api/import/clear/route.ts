import { NextResponse } from 'next/server'
import { prisma } from '../../../../lib/db'

export async function DELETE() {
  try {
    // Delete all imported data (this will cascade to slots due to the relation)
    await prisma.importedData.deleteMany()
    
    return NextResponse.json({ success: true, message: 'All data cleared successfully' })
  } catch (error) {
    console.error('Error clearing data:', error)
    return NextResponse.json(
      { success: false, error: 'Failed to clear data' },
      { status: 500 }
    )
  }
}
