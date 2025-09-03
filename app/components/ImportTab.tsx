'use client'

import React, { useState, useEffect } from 'react'
import { Upload, FileText, CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react'
import * as XLSX from 'xlsx'
import { supabase, DEFAULT_LEAGUE_ID } from '../../lib/supabase'

interface ImportTabProps {
  uploadedFile: File | null
  setUploadedFile: (file: File | null) => void
  slots: any[]
  setSlots: (slots: any[]) => void
  emlThresholds: {
    earlyStart: string
    midStart: string
  }
}

export default function ImportTab({ uploadedFile, setUploadedFile, slots, setSlots, emlThresholds }: ImportTabProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [excelData, setExcelData] = useState<any[]>(slots)
  const [headers, setHeaders] = useState<string[]>([])
  const [isFileFormatOpen, setIsFileFormatOpen] = useState(false)

  // Debug logging
  console.log('🔍 ImportTab received emlThresholds:', emlThresholds)
  console.log('🔍 emlThresholds.earlyStart:', emlThresholds?.earlyStart)
  console.log('🔍 emlThresholds.midStart:', emlThresholds?.midStart)

  // Load data from Supabase on component mount ONLY if no CSV data exists
  useEffect(() => {
    console.log('🚀 ImportTab mounted, checking if CSV data exists...')
    console.log('🔍 Current excelData length:', excelData.length)
    console.log('🔍 Current slots prop length:', slots.length)
    
    // If we have slots data from props, use that
    if (slots.length > 0) {
      console.log('📊 Using slots data from props:', slots.length, 'slots')
      setExcelData(slots)
      setHeaders(['Type', 'Event Start', 'Event End', 'Resource'])
      // Don't set a generic filename when loading from existing data
      setUploadedFile(null)
      return
    }
    
    // If no slots data and no excelData, try to load from Supabase
    if (excelData.length === 0) {
      console.log('📊 No CSV data found, loading from Supabase...')
      loadFromSupabase()
    } else {
      console.log('📊 CSV data already exists, skipping Supabase load')
    }
  }, [slots.length, excelData.length]) // Run when either slots or excelData changes

  const loadFromSupabase = async () => {
    console.log('🔄 Loading data from Supabase...')
    if (!supabase) {
      console.log('❌ Supabase not available')
      setError('Database connection not available')
      return
    }
    
    try {
      // Load slots directly (no import records in new schema)
      const { data: slotsData, error: slotsError } = await supabase
        .from('slots')
        .select('*')
        .eq('league_id', DEFAULT_LEAGUE_ID)
        .order('event_start')

      if (slotsError) {
        console.error('❌ Error loading slots:', slotsError)
        setError('Failed to load slots from database')
        return
      }

      if (slotsData && slotsData.length > 0) {
        console.log('✅ Loaded', slotsData.length, 'slots from Supabase')
        
        console.log('🔍 Processing slotsData:', slotsData.length, 'slots')
        console.log('🔍 First slot example:', slotsData[0])
        
        // Convert slots back to array format
        const convertedData = slotsData.map((slot: any) => {
          // Parse ISO timestamps and convert to display format
          const formatDateTime = (isoString: string) => {
            if (!isoString) return ''
            
            try {
              // Parse the UTC timestamp but treat it as if it was the original local time
              const utcDate = new Date(isoString)
              if (isNaN(utcDate.getTime())) return isoString
              
              // Convert back to local time by adding the timezone offset
              const localDate = new Date(utcDate.getTime() + (utcDate.getTimezoneOffset() * 60000))
              
              // Format as MM/DD/YY HH:MM AM/PM
              const month = (localDate.getMonth() + 1).toString().padStart(2, '0')
              const day = localDate.getDate().toString().padStart(2, '0')
              const year = localDate.getFullYear().toString().slice(-2)
              const hours = localDate.getHours()
              const minutes = localDate.getMinutes().toString().padStart(2, '0')
              const ampm = hours >= 12 ? 'PM' : 'AM'
              const displayHours = hours % 12 || 12
              
              return `${month}/${day}/${year} ${displayHours}:${minutes} ${ampm}`
            } catch (error) {
              console.error('Error formatting date:', error)
              return isoString
            }
          }
          
          // Parse the event_start timestamp to extract both date and time
          let date = ''
          let timeStart = ''
          let timeEnd = ''
          
          try {
            // Parse the event_start timestamp
            const utcDate = new Date(slot.event_start)
            if (!isNaN(utcDate.getTime())) {
              // Convert to local time
              const localDate = new Date(utcDate.getTime() + (utcDate.getTimezoneOffset() * 60000))
              
              // Extract date for the date column (MM/DD/YY)
              const month = (localDate.getMonth() + 1).toString().padStart(2, '0')
              const day = localDate.getDate().toString().padStart(2, '0')
              const year = localDate.getFullYear().toString().slice(-2)
              date = `${month}/${day}/${year}`
              
              // Extract time for the Event Start column (HH:MM AM/PM)
              const hours = localDate.getHours()
              const minutes = localDate.getMinutes().toString().padStart(2, '0')
              const ampm = hours >= 12 ? 'PM' : 'AM'
              const displayHours = hours % 12 || 12
              timeStart = `${displayHours}:${minutes} ${ampm}`
            }
          } catch (error) {
            console.error('Error parsing event_start:', error)
          }
          
          // Parse the event_end timestamp for the Event End column
          try {
            const utcEndDate = new Date(slot.event_end)
            if (!isNaN(utcEndDate.getTime())) {
              const localEndDate = new Date(utcEndDate.getTime() + (utcEndDate.getTimezoneOffset() * 60000))
              
              const hours = localEndDate.getHours()
              const minutes = localEndDate.getMinutes().toString().padStart(2, '0')
              const ampm = hours >= 12 ? 'PM' : 'AM'
              const displayHours = hours % 12 || 12
              timeEnd = `${displayHours}:${minutes} ${ampm}`
            }
          } catch (error) {
            console.error('Error parsing event_end:', error)
          }
          
          return [
            date, // Type column (date) - MM/DD/YY format
            timeStart, // Event Start column (just time) - HH:MM AM/PM format
            timeEnd, // Event End column (just time) - HH:MM AM/PM format
            slot.resource // Resource column
          ]
        })
        
        // Sort the data by date and time
        const sortedData = convertedData.sort((a, b) => {
          const dateA = a[0] // Type column (date)
          const dateB = b[0]
          const timeA = a[1] // Event Start column
          const timeB = b[1]
          
          // Parse dates (MM/DD/YY format)
          const parseDate = (dateStr: string) => {
            if (!dateStr || typeof dateStr !== 'string') return new Date(0)
            const parts = dateStr.split('/')
            if (parts.length === 3) {
              const month = parseInt(parts[0]) - 1
              const day = parseInt(parts[1])
              const year = 2000 + parseInt(parts[2])
              return new Date(year, month, day)
            }
            return new Date(0)
          }
          
          // Parse time (HH:MM AM/PM format)
          const parseTime = (timeStr: string) => {
            if (!timeStr || typeof timeStr !== 'string') return 0
            const timeMatch = timeStr.match(/(\d+):(\d+)\s*(AM|PM)/)
            if (!timeMatch) return 0
            
            let hours = parseInt(timeMatch[1])
            const minutes = parseInt(timeMatch[2])
            const ampm = timeMatch[3]
            
            if (ampm === 'PM' && hours !== 12) hours += 12
            if (ampm === 'AM' && hours === 12) hours = 0
            
            return hours * 60 + minutes
          }
          
          const dateAObj = parseDate(dateA)
          const dateBObj = parseDate(dateB)
          
          // First compare by date
          if (dateAObj.getTime() !== dateBObj.getTime()) {
            return dateAObj.getTime() - dateBObj.getTime()
          }
          
          // If dates are the same, compare by time
          const timeAMinutes = parseTime(timeA)
          const timeBMinutes = parseTime(timeB)
          return timeAMinutes - timeBMinutes
        })
        
        // Update the UI with Supabase data
        setExcelData(sortedData)
        setSlots(sortedData)
        // Don't set a generic filename when loading from existing data
        setUploadedFile(null)
        setHeaders(['Type', 'Event Start', 'Event End', 'Resource'])
        setError(null) // Clear any previous errors
        
        console.log('✅ Data loaded from Supabase successfully - UI updated')
        console.log('📊 Current data count:', convertedData.length, 'rows')
      } else {
        console.log('⚠️ No slots found in Supabase')
        showNoDataMessage()
      }
    } catch (error) {
      console.error('❌ Error loading from Supabase:', error)
      setError('Failed to load data from database')
    }
  }

  const showNoDataMessage = () => {
    setExcelData([])
    setSlots([])
    setUploadedFile(null)
    setHeaders([])
    setError('No current data. Please upload a file to get started.')
  }

  const saveToSupabase = async (fileName: string, data: any[], headers: string[]) => {
    if (!supabase) {
      console.log('❌ Supabase not available')
      setError('Database connection not available')
      return
    }
    
    try {
      console.log('🗑️ Clearing ALL existing data from Supabase...')
      
      // Delete ALL existing data (no conditions)
      const { error: deleteSlotsError } = await supabase
        .from('slots')
        .delete()
        .eq('league_id', DEFAULT_LEAGUE_ID) // Delete slots for this league

      if (deleteSlotsError) {
        throw new Error(`Failed to delete existing slots: ${deleteSlotsError.message}`)
      }
      
      console.log('✅ Cleared ALL existing data')

      // Sort data by date and time before inserting
      console.log('📊 Sorting', data.length, 'slots by date and time...')
      
      const sortedData = [...data].sort((a, b) => {
        // Parse dates for comparison
        const parseDateForSort = (dateStr: string) => {
          if (!dateStr) return new Date(0)
          const parts = dateStr.split('/')
          if (parts.length === 3) {
            const month = parseInt(parts[0]) - 1
            const day = parseInt(parts[1])
            const year = 2000 + parseInt(parts[2])
            return new Date(year, month, day)
          }
          return new Date(dateStr)
        }
        
        const parseTimeForSort = (timeStr: string) => {
          if (!timeStr) return 0
          const timeMatch = timeStr.match(/(\d+):(\d+)\s*(AM|PM)/)
          if (!timeMatch) return 0
          
          let hours = parseInt(timeMatch[1])
          const minutes = parseInt(timeMatch[2])
          const ampm = timeMatch[3]
          if (ampm === 'PM' && hours !== 12) hours += 12
          if (ampm === 'AM' && hours === 12) hours = 0
          
          return hours * 60 + minutes
        }
        
        const dateA = parseDateForSort(a[0] || '')
        const dateB = parseDateForSort(b[0] || '')
        
        // First compare by date
        if (dateA.getTime() !== dateB.getTime()) {
          return dateA.getTime() - dateB.getTime()
        }
        
        // If dates are the same, compare by time
        const timeA = parseTimeForSort(a[1] || '')
        const timeB = parseTimeForSort(b[1] || '')
        return timeA - timeB
      })
      
      console.log('📊 Converting and inserting', sortedData.length, 'sorted slots...')
      
      // Convert date and time strings to proper ISO timestamps
      const slotsToInsert = sortedData.map((row, index) => {
        const dateStr = row[0] || '' // Date column
        const startTimeStr = row[1] || '' // Event Start column
        const endTimeStr = row[2] || '' // Event End column
        const resource = row[3] || '' // Resource column
        
        // Parse date (MM/DD/YY or MM/DD/YYYY format)
        const parseDate = (dateStr: string) => {
          if (!dateStr) return null
          const parts = dateStr.split('/')
          if (parts.length === 3) {
            const month = parseInt(parts[0]) - 1
            const day = parseInt(parts[1])
            const yearPart = parseInt(parts[2])
            // Handle both 2-digit (YY) and 4-digit (YYYY) years
            const year = yearPart < 100 ? 2000 + yearPart : yearPart
            return new Date(year, month, day)
          }
          return null
        }
        
        // Parse time (HH:MM AM/PM format) and combine with date
        const parseDateTime = (dateStr: string, timeStr: string) => {
          const date = parseDate(dateStr)
          if (!date || !timeStr) return null
          
          const timeMatch = timeStr.match(/(\d+):(\d+)\s*(AM|PM)/)
          if (!timeMatch) return null
          
          let hours = parseInt(timeMatch[1])
          const minutes = parseInt(timeMatch[2])
          const ampm = timeMatch[3]
          
          if (ampm === 'PM' && hours !== 12) hours += 12
          if (ampm === 'AM' && hours === 12) hours = 0
          
          // Create a date in the local timezone
          const localDate = new Date(date.getFullYear(), date.getMonth(), date.getDate(), hours, minutes, 0, 0)
          
          // Convert to UTC ISO string for Supabase storage
          // We need to SUBTRACT the timezone offset to convert local time to UTC
          const utcDate = new Date(localDate.getTime() - (localDate.getTimezoneOffset() * 60000))
          return utcDate.toISOString()
        }
        
        const eventStart = parseDateTime(dateStr, startTimeStr)
        const eventEnd = parseDateTime(dateStr, endTimeStr)
        
        return {
          league_id: DEFAULT_LEAGUE_ID,
          type: 'game', // Default type
          event_start: eventStart,
          event_end: eventEnd,
          resource: resource
        }
      }).filter(slot => slot.event_start && slot.event_end) // Only include slots with valid timestamps

      console.log('📊 Inserting', slotsToInsert.length, 'valid slots...')
      
      const { error: slotsError } = await supabase
        .from('slots')
        .insert(slotsToInsert)

      if (slotsError) {
        throw new Error(`Failed to insert slots: ${slotsError.message}`)
      }

      console.log('✅ Successfully saved', slotsToInsert.length, 'slots to Supabase')
      
      // Immediately reload the data from Supabase to display it
      await loadFromSupabase()
      
    } catch (error) {
      console.error('❌ Error saving to Supabase:', error)
      setError(`Failed to save data: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }



  const clearData = () => {
    setExcelData([])
    setSlots([])
    setUploadedFile(null)
    setHeaders([])
    setError(null)
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    console.log('File selected:', file.name)
    setIsLoading(true)
    setError(null)
    setUploadedFile(file)

    try {
      const data = await readExcelFile(file)
      console.log('Raw Excel data:', data)
      
      if (data.length === 0) {
        throw new Error('Excel file is empty')
      }

      const excelHeaders = data[0] as string[]
      const excelRows = data.slice(1) as any[][]
      
      // Only convert date columns, leave others as strings
      const dateColumns = ['Event Start', 'Event End'] // Only these columns should be treated as dates
      
      // Also handle the Type column which might contain dates
      const typeColumnIndex = excelHeaders.indexOf('Type')
      const eventStartColumnIndex = excelHeaders.indexOf('Event Start')
      
      const convertExcelDate = (value: any): string => {
        console.log(`Processing value: ${value} (type: ${typeof value})`)
        
        let date: Date
        
        if (value instanceof Date) {
          // Already a Date object
          date = value
          console.log(`Value is already a Date: ${date}`)
        } else if (typeof value === 'number' || (typeof value === 'string' && !isNaN(Number(value)))) {
          // Excel serial date number
          const numValue = Number(value)
          console.log(`Converting Excel serial number: ${numValue}`)
          date = new Date((numValue - 25569) * 86400 * 1000)
          console.log(`Converted to date: ${date}`)
        } else {
          // Try parsing as a date string
          console.log(`Trying to parse as date string: ${value}`)
          date = new Date(value)
          console.log(`Parsed date: ${date}`)
        }
        
        // Check if date is valid
        if (isNaN(date.getTime())) {
          console.log(`Invalid date, returning original value: ${value}`)
          return String(value)
        }
        
        // Check if this is just a date (time is midnight) or has actual time
        const hours = date.getHours()
        const minutes = date.getMinutes()
        
        // For Event Start/End columns, always show full date and time
        const month = (date.getMonth() + 1).toString().padStart(2, '0')
        const day = date.getDate().toString().padStart(2, '0')
        const year = date.getFullYear().toString().slice(-2)
        const minutesStr = minutes.toString().padStart(2, '0')
        const ampm = hours >= 12 ? 'PM' : 'AM'
        const displayHours = hours % 12 || 12
        
        const result = `${month}/${day}/${year} ${displayHours}:${minutesStr} ${ampm}`
        console.log(`Date and time result: ${result}`)
        return result
      }
      
      const convertedRows = excelRows.map(row => 
        row.map((cell, colIndex) => {
          const header = excelHeaders[colIndex]
          
          // Handle Type column specially - if it's a date, convert it
          if (colIndex === typeColumnIndex) {
            if (typeof cell === 'number' || (typeof cell === 'string' && !isNaN(Number(cell)))) {
              // It's a date serial number, convert it
              const date = new Date((Number(cell) - 25569) * 86400 * 1000)
              const month = (date.getMonth() + 1).toString().padStart(2, '0')
              const day = date.getDate().toString().padStart(2, '0')
              const year = date.getFullYear().toString().slice(-2)
              return `${month}/${day}/${year}`
            }
            return String(cell)
          }
          
          // Only convert date columns, leave others as strings
          if (dateColumns.includes(header)) {
            return convertExcelDate(cell)
          } else {
            return String(cell) // Return as string for non-date columns
          }
        })
      )
      
      // Sort the data by date and time
      const sortedRows = convertedRows.sort((a, b) => {
        const dateA = a[typeColumnIndex] // Date column
        const dateB = b[typeColumnIndex]
        const timeA = a[eventStartColumnIndex] // Event Start column
        const timeB = b[eventStartColumnIndex]
        
        // Parse dates (MM/DD/YY format)
        const parseDate = (dateStr: string) => {
          if (!dateStr || typeof dateStr !== 'string') return new Date(0)
          const parts = dateStr.split('/')
          if (parts.length === 3) {
            const month = parseInt(parts[0]) - 1
            const day = parseInt(parts[1])
            const year = 2000 + parseInt(parts[2])
            return new Date(year, month, day)
          }
          return new Date(0)
        }
        
        // Parse time (HH:MM AM/PM format)
        const parseTime = (timeStr: string) => {
          if (!timeStr || typeof timeStr !== 'string') return 0
          const timeMatch = timeStr.match(/(\d+):(\d+)\s*(AM|PM)/)
          if (!timeMatch) return 0
          
          let hours = parseInt(timeMatch[1])
          const minutes = parseInt(timeMatch[2])
          const ampm = timeMatch[3]
          
          if (ampm === 'PM' && hours !== 12) hours += 12
          if (ampm === 'AM' && hours === 12) hours = 0
          
          return hours * 60 + minutes
        }
        
        const dateAObj = parseDate(dateA)
        const dateBObj = parseDate(dateB)
        
        // First compare by date
        if (dateAObj.getTime() !== dateBObj.getTime()) {
          return dateAObj.getTime() - dateBObj.getTime()
        }
        
        // If dates are the same, compare by time
        const timeAMinutes = parseTime(timeA)
        const timeBMinutes = parseTime(timeB)
        return timeAMinutes - timeBMinutes
      })
      
      // Save to Supabase and let it handle the formatting
      await saveToSupabase(file.name, convertedRows, excelHeaders)
      
      // Force reload from Supabase to get properly formatted data
      await loadFromSupabase()
      
      console.log('✅ CSV saved to Supabase, now using Supabase data for display')
    } catch (err) {
      console.error('Error processing file:', err)
      setError(err instanceof Error ? err.message : 'Failed to process file')
    } finally {
      setIsLoading(false)
    }
  }

  const readExcelFile = (file: File): Promise<any[]> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          console.log('File read successfully, processing...')
          const data = new Uint8Array(e.target?.result as ArrayBuffer)
          const workbook = XLSX.read(data, { type: 'array' })
          console.log('Workbook sheets:', workbook.SheetNames)
          
          const sheetName = workbook.SheetNames[0]
          const worksheet = workbook.Sheets[sheetName]
          const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 })
          console.log('Excel data converted to JSON:', jsonData)
          resolve(jsonData)
        } catch (error) {
          console.error('Error reading Excel file:', error)
          reject(new Error('Failed to read Excel file'))
        }
      }
      reader.onerror = (error) => {
        console.error('FileReader error:', error)
        reject(new Error('Failed to read file'))
      }
      reader.readAsArrayBuffer(file)
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Upload className="w-6 h-6" />
          Import Data
        </h2>
      </div>

      {/* File Format Instructions */}
      <div className="bg-gray-800 rounded-lg p-6">
        <button
          onClick={() => setIsFileFormatOpen(!isFileFormatOpen)}
          className="w-full flex items-center justify-between text-left"
        >
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Expected File Format
          </h3>
          {isFileFormatOpen ? (
            <ChevronUp className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          )}
        </button>
        
        {isFileFormatOpen && (
          <div className="text-sm text-gray-300 space-y-3 mt-4">
            <p>Your Excel file should have the following structure:</p>
            <div className="overflow-x-auto">
              <table className="min-w-full border border-gray-600 rounded">
                <thead>
                  <tr className="bg-gray-700">
                    <th className="px-4 py-2 text-left border-b border-gray-600">Date</th>
                    <th className="px-4 py-2 text-left border-b border-gray-600">Event Start</th>
                    <th className="px-4 py-2 text-left border-b border-gray-600">Event End</th>
                    <th className="px-4 py-2 text-left border-b border-gray-600">Resource</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="px-4 py-2 border-b border-gray-600">9/6/25</td>
                    <td className="px-4 py-2 border-b border-gray-600">9:00 PM</td>
                    <td className="px-4 py-2 border-b border-gray-600">10:20 PM</td>
                    <td className="px-4 py-2 border-b border-gray-600">GPI - Rink 4</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2 border-b border-gray-600">9/6/25</td>
                    <td className="px-4 py-2 border-b border-gray-600">10:15 PM</td>
                    <td className="px-4 py-2 border-b border-gray-600">11:35 PM</td>
                    <td className="px-4 py-2 border-b border-gray-600">GPI - Rink 2</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2">9/9/25</td>
                    <td className="px-4 py-2">9:35 PM</td>
                    <td className="px-4 py-2">10:55 PM</td>
                    <td className="px-4 py-2">GPI - Rink 3</td>
                  </tr>
                </tbody>
              </table>
            </div>

          </div>
        )}
      </div>

      {/* Upload Button */}
      <div className="flex justify-center">
        <label className="cursor-pointer">
          <input
            type="file"
            accept=".xlsx,.xls,.csv"
            onChange={handleFileUpload}
            className="hidden"
            disabled={isLoading}
          />
          <div className="bg-red-600 hover:bg-red-700 disabled:bg-gray-600 px-6 py-3 rounded-lg font-medium flex items-center gap-2 transition-colors">
            <Upload className="w-5 h-5" />
            {isLoading ? 'Processing...' : 'Upload CSV'}
          </div>
        </label>
      </div>

      {/* Status Messages */}
      {uploadedFile && (
        <div className="flex items-center gap-2 text-green-400">
          <CheckCircle className="w-5 h-5" />
          <span>File uploaded: {uploadedFile.name}</span>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 text-red-400">
          <XCircle className="w-5 h-5" />
          <span>Error loading file: {error}</span>
        </div>
      )}

      {/* No Data Message */}
      {excelData.length === 0 && !isLoading && (
        <div className="bg-gray-800 rounded-lg p-8 text-center">
          <div className="text-gray-400 mb-4">
            <FileText className="w-16 h-16 mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Current Data</h3>
            <p className="text-sm">Upload a file to get started with your league scheduling.</p>
          </div>
        </div>
      )}

      {/* Excel Data Table */}
      {excelData.length > 0 && (
        <div className="space-y-4">

          


          {/* Summary Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="bg-gray-800 p-4 rounded-lg">
              <div className="text-2xl font-bold">{excelData.length}</div>
              <div className="text-sm text-gray-400">Total Games</div>
            </div>
            <div className="bg-gray-800 p-4 rounded-lg">
              <div className="text-2xl font-bold">
                {(() => {
                  if (excelData.length === 0) return 'N/A'
                  
                  // Extract date from the first column (date column) instead of Event Start column
                  const startDateStr = excelData[0][0] // Date column, first row
                  
                  // Handle ISO timestamp format
                  if (startDateStr && startDateStr.includes('T')) {
                    try {
                      const date = new Date(startDateStr)
                      return date.toLocaleDateString()
                    } catch (e) {
                      return 'N/A'
                    }
                  }
                  
                  // Handle MM/DD/YY format (date column should just be date, not date+time)
                  if (startDateStr && typeof startDateStr === 'string') {
                    const parts = startDateStr.split('/')
                    if (parts.length === 3) {
                      const month = parseInt(parts[0])
                      const day = parseInt(parts[1])
                      const year = 2000 + parseInt(parts[2])
                      return `${month}/${day}/${year}`
                    }
                  }
                  
                  return 'N/A'
                })()}
              </div>
              <div className="text-sm text-gray-400">Start Date</div>
            </div>
            <div className="bg-gray-800 p-4 rounded-lg">
              <div className="text-2xl font-bold">
                {(() => {
                  if (excelData.length === 0) return 'N/A'
                  
                  // Extract date from the first column (date column) instead of Event Start column
                  const endDateStr = excelData[excelData.length - 1][0] // Date column, last row
                  
                  // Handle ISO timestamp format
                  if (endDateStr && endDateStr.includes('T')) {
                    try {
                      const date = new Date(endDateStr)
                      return date.toLocaleDateString()
                    } catch (e) {
                      return 'N/A'
                    }
                  }
                  
                  // Handle MM/DD/YY format (date column should just be date, not date+time)
                  if (endDateStr && typeof endDateStr === 'string') {
                    const parts = endDateStr.split('/')
                    if (parts.length === 3) {
                      const month = parseInt(parts[0])
                      const day = parseInt(parts[1])
                      const year = 2000 + parseInt(parts[2])
                      return `${month}/${day}/${year}`
                    }
                  }
                  
                  return 'N/A'
                })()}
              </div>
              <div className="text-sm text-gray-400">End Date</div>
            </div>
            <div className="bg-gray-800 p-4 rounded-lg">
              <div className="text-2xl font-bold">
                {(() => {
                  if (excelData.length === 0) return 'N/A'
                  
                  // Use the first column (index 0) for date, which should be the date column
                  // This is more reliable than depending on headers array
                  const startDateStr = excelData[0][0] // First column, first row
                  const endDateStr = excelData[excelData.length - 1][0] // First column, last row
                  
                  // Parse dates (assuming MM/DD/YY format)
                  const parseDate = (dateStr: string) => {
                    if (!dateStr || typeof dateStr !== 'string') return null
                    const parts = dateStr.split('/')
                    if (parts.length === 3) {
                      const month = parseInt(parts[0]) - 1 // Month is 0-indexed
                      const day = parseInt(parts[1])
                      const year = 2000 + parseInt(parts[2]) // Assuming 20xx years
                      return new Date(year, month, day)
                    }
                    return null
                  }
                  
                  const startDate = parseDate(startDateStr)
                  const endDate = parseDate(endDateStr)
                  
                  if (startDate && endDate) {
                    const timeDiff = endDate.getTime() - startDate.getTime()
                    const daysDiff = Math.ceil(timeDiff / (1000 * 3600 * 24))
                    const weeksDiff = Math.ceil(daysDiff / 7)
                    return Math.max(1, weeksDiff) // Ensure at least 1 week
                  } else if (startDate) {
                    // If we only have a start date, assume 1 week
                    return 1
                  }
                  
                  return 'N/A'
                })()}
              </div>
              <div className="text-sm text-gray-400">Weeks</div>
            </div>
            <div className="bg-gray-800 p-4 rounded-lg">
              <div className="text-2xl font-bold">
                {(() => {
                                    // Calculate E/M/L categories in the UI - using the same logic as ScheduleTab
                  const getEMLCategory = (timeStr: string) => {
                    // Safety check for emlThresholds
                    if (!emlThresholds || !emlThresholds.earlyStart || !emlThresholds.midStart) {
                      console.warn('⚠️ emlThresholds not properly initialized:', emlThresholds)
                      return 'Unknown'
                    }

                    // Use earlyStart/midStart from emlThresholds
                    const earlyStart = emlThresholds.earlyStart || '22:01'
                    const midStart = emlThresholds.midStart || '22:31'
                    
                    // Extract just the time part from strings like "9:00 PM"
                    const timeOnly = timeStr.includes(' ') ? timeStr.split(' ').slice(-2).join(' ') : timeStr
                    console.log('🔍 Original timeStr:', timeStr, 'Extracted timeOnly:', timeOnly)
                    const timeMatch = timeOnly.match(/(\d+):(\d+)\s*(AM|PM)/)
                    if (!timeMatch) {
                      console.warn('⚠️ Failed to parse time:', timeStr, 'timeOnly:', timeOnly)
                      return 'Unknown'
                    }
                    
                    // Convert 12-hour format to 24-hour format for EML comparison
                    let hours = parseInt(timeMatch[1])
                    let minutes = parseInt(timeMatch[2])
                    const ampm = timeMatch[3]
                    
                    if (ampm === 'PM' && hours !== 12) hours += 12
                    if (ampm === 'AM' && hours === 12) hours = 0
                    
                    const gameMinutes = hours * 60 + minutes
                    console.log('🔍 Converted to 24-hour:', { hours, minutes, gameMinutes })
                    
                    // Parse thresholds - EML thresholds are in 24-hour format (22:01, 22:31)
                    let earlyMinutesTotal = 0
                    let midMinutesTotal = 0
                    
                    // Parse 24-hour format thresholds (e.g., "22:01", "22:31")
                    const early24Match = earlyStart.match(/^(\d{1,2}):(\d{2})$/)
                    const mid24Match = midStart.match(/^(\d{1,2}):(\d{2})$/)
                    
                    if (early24Match && mid24Match) {
                      // 24-hour format
                      earlyMinutesTotal = parseInt(early24Match[1]) * 60 + parseInt(early24Match[2])
                      midMinutesTotal = parseInt(mid24Match[1]) * 60 + parseInt(mid24Match[2])
                      console.log('🔍 EML thresholds (24-hour):', { earlyStart, midStart, earlyMinutesTotal, midMinutesTotal })
                    } else {
                      console.warn('⚠️ EML thresholds not in expected 24-hour format:', { earlyStart, midStart })
                      return 'Unknown'
                    }
                    
                    // Categorize based on 24-hour time comparison
                    // Early: before 22:01 (10:01 PM)
                    // Mid: between 22:01 (10:01 PM) and 22:31 (10:31 PM)
                    // Late: after 22:31 (10:31 PM)
                    if (gameMinutes < earlyMinutesTotal) return 'Early'
                    if (gameMinutes >= earlyMinutesTotal && gameMinutes < midMinutesTotal) return 'Mid'
                    return 'Late'
                  }
                  
                  const earlyCount = excelData.filter(row => {
                    const timeStr = row[1] || '' // Event Start time
                    return getEMLCategory(timeStr) === 'Early'
                  }).length
                  
                  const midCount = excelData.filter(row => {
                    const timeStr = row[1] || '' // Event Start time
                    return getEMLCategory(timeStr) === 'Mid'
                  }).length
                  
                  const lateCount = excelData.filter(row => {
                    const timeStr = row[1] || '' // Event Start time
                    return getEMLCategory(timeStr) === 'Late'
                  }).length
                  
                  return `${earlyCount} / ${midCount} / ${lateCount}`
                })()}
              </div>
              <div className="text-sm text-gray-400">E / M / L</div>
            </div>

          </div>

          {/* Raw Excel Table */}
          <div className="bg-gray-800 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">

              <table className="min-w-full">
                <thead className="bg-gray-700">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      DATE
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      EVENT START
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      EVENT END
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      RESOURCE
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                      E/M/L
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {excelData.map((row, rowIndex) => {
                    // Calculate E/M/L category in the UI - using the same logic as ScheduleTab
                    const getEMLCategory = (timeStr: string) => {
                      // Safety check for emlThresholds
                      if (!emlThresholds || !emlThresholds.earlyStart || !emlThresholds.midStart) {
                        console.warn('⚠️ emlThresholds not properly initialized:', emlThresholds)
                        return 'Unknown'
                      }

                      // Use earlyStart/midStart from emlThresholds
                      const earlyStart = emlThresholds.earlyStart || '22:01'
                      const midStart = emlThresholds.midStart || '22:31'
                      
                      // Extract just the time part from strings like "9:00 PM"
                      const timeOnly = timeStr.includes(' ') ? timeStr.split(' ').slice(-2).join(' ') : timeStr
                      console.log('🔍 Original timeStr:', timeStr, 'Extracted timeOnly:', timeOnly)
                      const timeMatch = timeOnly.match(/(\d+):(\d+)\s*(AM|PM)/)
                      if (!timeMatch) {
                        console.warn('⚠️ Failed to parse time:', timeStr, 'timeOnly:', timeOnly)
                        return 'Unknown'
                      }
                      
                      // Convert 12-hour format to 24-hour format for EML comparison
                      let hours = parseInt(timeMatch[1])
                      let minutes = parseInt(timeMatch[2])
                      const ampm = timeMatch[3]
                      
                      if (ampm === 'PM' && hours !== 12) hours += 12
                      if (ampm === 'AM' && hours === 12) hours = 0
                      
                      const gameMinutes = hours * 60 + minutes
                      console.log('🔍 Converted to 24-hour:', { hours, minutes, gameMinutes })
                      
                      // Parse thresholds - EML thresholds are in 24-hour format (22:01, 22:31)
                      let earlyMinutesTotal = 0
                      let midMinutesTotal = 0
                      
                      // Parse 24-hour format thresholds (e.g., "22:01", "22:31")
                      const early24Match = earlyStart.match(/^(\d{1,2}):(\d{2})$/)
                      const mid24Match = midStart.match(/^(\d{1,2}):(\d{2})$/)
                      
                      if (early24Match && mid24Match) {
                        // 24-hour format
                        earlyMinutesTotal = parseInt(early24Match[1]) * 60 + parseInt(early24Match[2])
                        midMinutesTotal = parseInt(mid24Match[1]) * 60 + parseInt(mid24Match[2])
                        console.log('🔍 EML thresholds (24-hour):', { earlyStart, midStart, earlyMinutesTotal, midMinutesTotal })
                      } else {
                        console.warn('⚠️ EML thresholds not in expected 24-hour format:', { earlyStart, midStart })
                        return 'Unknown'
                      }
                      
                      // Categorize based on 24-hour time comparison
                      if (gameMinutes < earlyMinutesTotal) return 'Early'
                      if (gameMinutes >= earlyMinutesTotal && gameMinutes < midMinutesTotal) return 'Mid'
                      return 'Late'
                    }
                    
                    // Format the data for display
                    const formatDate = (dateStr: string) => {
                      if (!dateStr) return 'N/A'
                      
                      // Handle ISO timestamp format
                      if (dateStr.includes('T')) {
                        try {
                          const date = new Date(dateStr)
                          return date.toLocaleDateString()
                        } catch (e) {
                          return dateStr
                        }
                      }
                      
                      // Handle MM/DD/YY format
                      if (typeof dateStr === 'string') {
                        const parts = dateStr.split('/')
                        if (parts.length === 3) {
                          const month = parseInt(parts[0])
                          const day = parseInt(parts[1])
                          const year = 2000 + parseInt(parts[2])
                          return `${month}/${day}/${year}`
                        }
                      }
                      
                      return dateStr
                    }
                    
                    const formatTime = (timeStr: string) => {
                      if (!timeStr) return 'N/A'
                      
                      // Handle ISO timestamp format
                      if (timeStr.includes('T')) {
                        try {
                          const date = new Date(timeStr)
                          return date.toLocaleTimeString([], { 
                            hour: '2-digit', 
                            minute: '2-digit',
                            hour12: true 
                          })
                        } catch (e) {
                          return timeStr
                        }
                      }
                      
                      // If it's already in AM/PM format, return as is
                      return timeStr
                    }
                    
                    const timeStr = row[1] || '' // Event Start time
                    const emlCategory = getEMLCategory(timeStr)
                    
                    return (
                      <tr key={rowIndex} className="hover:bg-gray-700">
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          {formatDate(row[0])}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          {formatTime(row[1])}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          {formatTime(row[2])}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          {row[3] || ''}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <span className={`px-2 py-1 rounded text-xs ${
                            emlCategory === 'Early' ? 'bg-green-600' :
                            emlCategory === 'Mid' ? 'bg-yellow-600' : 'bg-red-600'
                          }`}>
                            {emlCategory}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
