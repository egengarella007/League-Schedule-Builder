'use client'

import React, { useState, useEffect, useRef } from 'react'
import { Calendar, Download, CheckCircle, RefreshCw, X, Zap, Loader2 } from 'lucide-react'
import { supabase, DEFAULT_LEAGUE_ID } from '@/lib/supabase'
import { SchedulerParamsData } from '@/lib/types'

interface ScheduleTabProps {
  slots: any[]
  teams: any[]
  divisions: any[]
  params: SchedulerParamsData
}



export default function ScheduleTab({ slots: propSlots, teams: propTeams, divisions: propDivisions, params }: ScheduleTabProps) {
  // Helper function to check for +0d games (back-to-back games with no rest)
  const hasZeroDayGames = (schedule: any[]) => {
    if (!schedule || schedule.length === 0) return false
    
    // Group games by team and date
    const teamDates = new Map<string, Set<string>>()
    
    schedule.forEach(game => {
      if (game.HomeTeam && game.AwayTeam && game.Date) {
        // Track home team games
        if (!teamDates.has(game.HomeTeam)) {
          teamDates.set(game.HomeTeam, new Set())
        }
        teamDates.get(game.HomeTeam)!.add(game.Date)
        
        // Track away team games
        if (!teamDates.has(game.AwayTeam)) {
          teamDates.set(game.AwayTeam, new Set())
        }
        teamDates.get(game.AwayTeam)!.add(game.Date)
      }
    })
    
    // Check for teams with multiple games on the same date
    teamDates.forEach((dates, team) => {
      if (dates.size < schedule.length) { // Only check if team has multiple games
        const dateArray = Array.from(dates).sort()
        for (let i = 0; i < dateArray.length - 1; i++) {
          const currentDate = new Date(dateArray[i] as string)
          const nextDate = new Date(dateArray[i + 1] as string)
          const daysDiff = Math.floor((nextDate.getTime() - currentDate.getTime()) / (1000 * 60 * 60 * 24))
          
          if (daysDiff === 0) {
            console.log(`🎯 WARNING: Team ${team} has +0d games on ${dateArray[i]} and ${dateArray[i + 1]}`)
            return true
          }
        }
      }
    })
    
    return false
  }
  
  // Helper function to find and return details about +0d games
  const findZeroDayGames = (schedule: any[]) => {
    if (!schedule || schedule.length === 0) return []
    
    const zeroDayIssues: Array<{team: string, date: string, games: any[]}> = []
    
    // Group games by team and date
    const teamDates = new Map<string, Map<string, any[]>>()
    
    schedule.forEach(game => {
      if (game.HomeTeam && game.AwayTeam && game.Date) {
        // Track home team games
        if (!teamDates.has(game.HomeTeam)) {
          teamDates.set(game.HomeTeam, new Map())
        }
        if (!teamDates.get(game.HomeTeam)!.has(game.Date)) {
          teamDates.get(game.HomeTeam)!.set(game.Date, [])
        }
        teamDates.get(game.HomeTeam)!.get(game.Date)!.push(game)
        
        // Track away team games
        if (!teamDates.has(game.AwayTeam)) {
          teamDates.set(game.AwayTeam, new Map())
        }
        if (!teamDates.get(game.AwayTeam)!.has(game.Date)) {
          teamDates.get(game.AwayTeam)!.set(game.Date, [])
        }
        teamDates.get(game.AwayTeam)!.get(game.Date)!.push(game)
      }
    })
    
    // Find teams with multiple games on the same date
    teamDates.forEach((dateMap, team) => {
      dateMap.forEach((games, date) => {
        if (games.length > 1) {
          zeroDayIssues.push({
            team,
            date,
            games: games
          })
        }
      })
    })
    
    return zeroDayIssues
  }
  
  // Helper function to calculate EML category from game START time
  const getEMLCategory = (gameTime: string) => {
    // Use earlyStart/midStart from params (now using START times)
    const earlyStart = params.eml?.earlyStart || '22:01'
    const midStart = params.eml?.midStart || '22:31'
    
    const timeMatch = gameTime.match(/(\d+):(\d+)\s*(AM|PM)/)
    if (!timeMatch) return 'Unknown'
    
    let hours = parseInt(timeMatch[1])
    let minutes = parseInt(timeMatch[2])
    const ampm = timeMatch[3]
    
    if (ampm === 'PM' && hours !== 12) hours += 12
    if (ampm === 'AM' && hours === 12) hours = 0
    
    const gameMinutes = hours * 60 + minutes
    
    // Parse thresholds - handle both 24-hour (22:01) and 12-hour (10:01 PM) formats
    let earlyMinutesTotal = 0
    let midMinutesTotal = 0
    
    // Try 24-hour format first (e.g., "22:01")
    const early24Match = earlyStart.match(/^(\d{1,2}):(\d{2})$/)
    const mid24Match = midStart.match(/^(\d{1,2}):(\d{2})$/)
    
    if (early24Match && mid24Match) {
      // 24-hour format
      earlyMinutesTotal = parseInt(early24Match[1]) * 60 + parseInt(early24Match[2])
      midMinutesTotal = parseInt(mid24Match[1]) * 60 + parseInt(mid24Match[2])
    } else {
      // 12-hour format (e.g., "10:01 PM")
      const earlyMatch = earlyStart.match(/(\d+):(\d+)\s*(AM|PM)/)
      const midMatch = midStart.match(/(\d+):(\d+)\s*(AM|PM)/)
      
      if (!earlyMatch || !midMatch) return 'Unknown'
      
      let earlyHours = parseInt(earlyMatch[1])
      let earlyMinutes = parseInt(earlyMatch[2])
      const earlyAmpm = earlyMatch[3]
      
      let midHours = parseInt(midMatch[1])
      let midMinutes = parseInt(midMatch[2])
      const midAmpm = midMatch[3]
      
      if (earlyAmpm === 'PM' && earlyHours !== 12) earlyHours += 12
      if (earlyAmpm === 'AM' && earlyHours === 12) earlyHours = 0
      if (midAmpm === 'PM' && midHours !== 12) midHours += 12
      if (midAmpm === 'AM' && midHours === 12) midHours = 0
      
      earlyMinutesTotal = earlyHours * 60 + earlyMinutes
      midMinutesTotal = midHours * 60 + midMinutes
    }
    
    if (gameMinutes < earlyMinutesTotal) return 'Early'
    if (gameMinutes >= earlyMinutesTotal && gameMinutes < midMinutesTotal) return 'Mid'
    return 'Late'
  }
  const [teams, setTeams] = useState<any[]>([])
  const [divisions, setDivisions] = useState<any[]>([])
  const [slots, setSlots] = useState<any[]>([])
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [currentSchedule, setCurrentSchedule] = useState<any[]>([])
  const [scheduleUrl, setScheduleUrl] = useState<string | null>(null)
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null)
  const [showTeamSchedule, setShowTeamSchedule] = useState(false)
  const [isOptimizing, setIsOptimizing] = useState(false)
  const [optimizationStats, setOptimizationStats] = useState<{ improvements: number } | null>(null)
  const [currentWeek, setCurrentWeek] = useState(2)  // Start with Week 2
  const [weeksOptimized, setWeeksOptimized] = useState<number[]>([])  // Track which weeks have been optimized
  const [allWeeksComplete, setAllWeeksComplete] = useState(false)  // Track if all weeks are complete
  const [totalOptimizableWeeks, setTotalOptimizableWeeks] = useState(0)  // Total weeks that can be optimized
  const [currentWeekImplemented, setCurrentWeekImplemented] = useState(false)  // Track if current week has been implemented
  const [shouldAutoOptimizeNext, setShouldAutoOptimizeNext] = useState(false)  // Track if we should auto-optimize the next week
  const [optimizationResults, setOptimizationResults] = useState<{
    schedule?: Array<{
      id: number
      start: string
      end: string
      rink: string
      div: string
      home: string
      away: string
    }>
    swaps?: Array<{
      block?: number
      division?: string
      game_i?: number
      game_j?: number
      delta_score?: number
      note: string
      original_home?: string
      original_away?: string
      new_home?: string
      new_away?: string
      time?: string
      game_id?: number
      phase?: string
      was_late?: boolean
      after?: string
      date?: string
      rink?: string
    }>
    score_before?: Record<string, number>
    score_after?: Record<string, number>
    buckets?: Record<string, Array<{
      Team: string
      E: number
      M: number
      L: number
      'Target E': number
      'Target M': number
      'Target L': number
      ΔE: number
      ΔM: number
      ΔL: number
      'Back-to-backs': number
      'Long gaps (>=10d)': number
      'Avg gap (d)': number | null
    }>>
    improvement?: number
    notes?: {
      method?: string
      blocks_processed?: number
      block_size?: number
      total_changes?: number
    }
  } | null>(null)
  const [showOptimizationModal, setShowOptimizationModal] = useState(false)

  const [isDaysOptimizing, setIsDaysOptimizing] = useState(false)
  const [daysOptimizeComplete, setDaysOptimizeComplete] = useState(false)
  const [currentDaysOptimizeWeek, setCurrentDaysOptimizeWeek] = useState<number | null>(null)
  
  // Ref to store the auto-optimization timer
  const autoOptimizeTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Load data on mount
  useEffect(() => {
    loadTeamsAndDivisions()
    loadSlots()
    loadParams()
  }, [])
  
  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (autoOptimizeTimerRef.current) {
        clearTimeout(autoOptimizeTimerRef.current)
        console.log('🎯 Cleaned up auto-optimization timer on unmount')
      }
    }
  }, [])
  
  // Simple auto-optimization: just chain to next week when current week completes
  useEffect(() => {
    if (shouldAutoOptimizeNext && !isOptimizing && currentWeek > 2) {
      console.log(`🎯 Auto-optimization: Starting Week ${currentWeek}`)
      setShouldAutoOptimizeNext(false) // Clear flag
      handleOptimizeSchedule() // Use existing, proven method
    }
  }, [shouldAutoOptimizeNext, isOptimizing, currentWeek])

  // Debug: Log whenever currentSchedule changes
  useEffect(() => {
    if (currentSchedule.length > 0) {
      console.log('🔄 Schedule updated - recalculating team counts:', {
        scheduleLength: currentSchedule.length,
        teamNames: Array.from(new Set([
          ...currentSchedule.map(g => g.HomeTeam),
          ...currentSchedule.map(g => g.AwayTeam)
        ])),
        sampleGames: currentSchedule.slice(0, 3)
      })
    }
  }, [currentSchedule])



  // Utility function to sort schedule chronologically
  const sortScheduleChronologically = (schedule: any[]) => {
    return [...schedule].sort((a, b) => {
      // Parse dates and times for proper chronological sorting
      const dateA = new Date(`${a.Date} ${a.Start}`)
      const dateB = new Date(`${b.Date} ${b.Start}`)
      return dateA.getTime() - dateB.getTime()
    })
  }







  const loadSlots = async () => {
    if (!supabase) return

    try {
      const { data: slotsData, error: slotsError } = await supabase
        .from('slots')
        .select('*')
        .eq('league_id', DEFAULT_LEAGUE_ID)
        .order('event_start', { ascending: true })

      if (slotsError) throw slotsError
      setSlots(slotsData || [])
      console.log('Loaded slots:', slotsData?.length || 0)
    } catch (error) {
      console.error('Error loading slots:', error)
    }
  }

  const loadParams = async () => {
    try {
      const response = await fetch('/api/parameters')
      if (response.ok) {
        const result = await response.json()
        if (result.success && result.data) {
          console.log('✅ Loaded parameters from server:', result.data)
          // Update the params prop if needed
        }
      }
    } catch (error) {
      console.error('Error loading parameters:', error)
    }
  }

  const handleTeamClick = (teamName: string) => {
    setSelectedTeam(teamName)
    setShowTeamSchedule(true)
  }

  const closeTeamSchedule = () => {
    setShowTeamSchedule(false)
    setSelectedTeam(null)
  }

  const handleOptimizeSchedule = async () => {
    if (!currentSchedule.length) return
    
    console.log(`🎯 handleOptimizeSchedule called for Week ${currentWeek}`)
    console.log(`🎯 Current state: currentWeek=${currentWeek}, weeksOptimized=${weeksOptimized.join(',')}, allWeeksComplete=${allWeeksComplete}`)
    
    setIsOptimizing(true)
    setOptimizationStats(null)
    setCurrentWeekImplemented(false)  // Reset implemented state for new week
    
    try {
      console.log('🔧 Starting optimization with schedule:', currentSchedule.length, 'games')
      
      // Use the schedule in its original order (the scheduler already created proper blocks)
      console.log('🔧 Using schedule in original order (scheduler already created proper blocks)')
      
      // Debug: Check what divisions we actually have
      const uniqueDivisions = Array.from(new Set(currentSchedule.map(g => g.Division)))
      console.log('🔧 Unique divisions in schedule:', uniqueDivisions)
      console.log('🔧 Sample games with divisions:')
      currentSchedule.slice(0, 10).forEach((game, i) => {
        console.log(`  ${i+1}. Div: "${game.Division}" - ${game.HomeTeam} vs ${game.AwayTeam}`)
      })
      
      // Group games into blocks of 10 (in original order)
      const blockSize = 10
      const blocks = []
      for (let i = 0; i < currentSchedule.length; i += blockSize) {
        const block = currentSchedule.slice(i, i + blockSize)
        if (block.length === blockSize) { // Only send complete blocks
          blocks.push(block)
        }
      }
      
      console.log('🔧 Total games:', currentSchedule.length)
      console.log('🔧 Block size:', blockSize)
      console.log('🔧 Found complete blocks:', blocks.length)
      
      if (blocks.length === 0) {
        setError(`Schedule must have complete blocks of ${blockSize} games for optimization. Found ${currentSchedule.length} total games.`)
        setIsOptimizing(false)
        return
      }
      
            // Check if the first block has the right division mix
      const firstBlock = blocks[0]
      const divCounts = firstBlock.reduce((acc, game) => {
        const div = game.Division?.toLowerCase().trim()
        if (div === 'Tin Super' || div?.includes('12')) {
          acc['Tin Super'] = (acc['Tin Super'] || 0) + 1
        } else if (div === 'Tin South' || div?.includes('8')) {
          acc['Tin South'] = (acc['Tin South'] || 0) + 1
        }
        return acc
      }, {})
      
      console.log('🔧 Processing ALL games for optimization (not just first block)')
      console.log('🔧 Total games to optimize:', currentSchedule.length)
      
      // Prepare schedule data for optimization (use ALL games to process all blocks)
      const scheduleData = currentSchedule.map((game, index) => {
          // Parse the date and time properly - preserve local time
          const gameDate = new Date(game.Date + ' ' + game.Start)
          const endTime = game.End || '22:20' // Default 80 min if no end time
          const endDate = new Date(game.Date + ' ' + endTime)
          
          // Determine division (normalize to 'a' or 'b')
          let div = 'unknown'
          if (game.Division) {
            const divLower = game.Division.toLowerCase().trim()
            // Handle both formats: 'Tin Super'/'Tin South' and '12 team'/'8 team'
            if (divLower === 'tin super' || divLower.includes('12')) div = 'Tin Super'
            else if (divLower === 'tin south' || divLower.includes('8')) div = 'Tin South'
            else div = 'unknown'
          }
          
          // Extract team number from team name (e.g., "Team 7" -> "7")
          const extractTeamNumber = (teamName: string) => {
            const match = teamName.match(/(\d+)$/)
            return match ? match[1] : teamName
          }
          
          // Convert to proper ISO string that preserves local time
          const formatLocalTime = (date: Date) => {
            // Get local time components
            const year = date.getFullYear()
            const month = String(date.getMonth() + 1).padStart(2, '0')
            const day = String(date.getDate()).padStart(2, '0')
            const hours = String(date.getHours()).padStart(2, '0')
            const minutes = String(date.getMinutes()).padStart(2, '0')
            
            // Create a simple ISO string without timezone info - let the backend handle it
            return `${year}-${month}-${day}T${hours}:${minutes}:00.000`
          }
          
          return {
            id: index + 1,
            start: formatLocalTime(gameDate), // Send as local time string
            end: formatLocalTime(endDate),    // Send as local time string
            rink: game.Rink || 'Unknown',
            div: div,
            home: extractTeamNumber(game.HomeTeam),
            away: extractTeamNumber(game.AwayTeam)
          }
        })

      console.log('🔧 Prepared schedule data:', scheduleData.slice(0, 3))
      console.log('🔧 Total games to optimize:', scheduleData.length)
      console.log('🔧 Division counts:', scheduleData.reduce((acc, game) => {
        acc[game.div] = (acc[game.div] || 0) + 1
        return acc
      }, {}))
      
      // Debug: Check the actual data structure being sent
      console.log('🔧 Sample game structure:', {
        sampleGame: scheduleData[0],
        sampleGameKeys: Object.keys(scheduleData[0] || {}),
        sampleGameValues: Object.values(scheduleData[0] || {})
      })
      
      // Debug: Check if games are in chronological order
      console.log('🔧 Game order check:')
      scheduleData.forEach((game, index) => {
        console.log(`  Game ${index + 1}: ${game.start} (ID: ${game.id}) - ${game.home} vs ${game.away} (${game.div})`)
      })
      
            // Debug: Check for any potential issues
      const hasUnknownDiv = scheduleData.some(g => g.div === 'unknown')
      console.log('🔧 Data validation:', { hasUnknownDiv })
      
      // Debug: Show sample games with readable times
      console.log('🔧 Sample games with readable times:')
      scheduleData.slice(0, 10).forEach((game, index) => {
        const startTime = new Date(game.start)
        const readableTime = startTime.toLocaleTimeString('en-US', { 
          hour: 'numeric', 
          minute: '2-digit', 
          hour12: true 
        })
        console.log(`  Game ${index + 1}: ${game.start} → ${readableTime} - ${game.home} vs ${game.away} (${game.div})`)
      })
      
      // Debug: Count late games (after 10:31 PM)
      const lateThreshold = new Date('2000-01-01T22:31:00') // 10:31 PM
      const lateGames = scheduleData.filter(game => {
        const startTime = new Date(game.start)
        return startTime.getHours() >= 22 && startTime.getMinutes() >= 31
      })
      console.log(`🔧 Late games found: ${lateGames.length} out of ${scheduleData.length} total games`)
      if (lateGames.length > 0) {
        console.log('🔧 Late games:')
        lateGames.slice(0, 5).forEach((game, index) => {
          const startTime = new Date(game.start)
          const readableTime = startTime.toLocaleTimeString('en-US', { 
            hour: 'numeric', 
            minute: '2-digit', 
            hour12: true 
          })
          console.log(`  Late Game ${index + 1}: ${game.start} → ${readableTime} - ${game.home} vs ${game.away} (${game.div})`)
        })
      }
      
      // Don't proceed if we have unknown divisions
      if (hasUnknownDiv) {
        setError('Cannot optimize schedule with unknown divisions. Please check division assignments.')
        setIsOptimizing(false)
        return
      }
      
      const requestBody = {
        schedule: scheduleData,
        blockSize: 10,
        blockRecipe: { 'Tin Super': 6, 'Tin South': 4 },
        divisionSizes: { 'Tin Super': 12, 'Tin South': 8 }, // Number of teams in each division
        earlyStart: "10:01 PM",  // ✅ Use START time for EML classification
        midStart: "10:31 PM",    // ✅ Use START time for EML classification
        target_week: currentWeek,  // 🎯 Target specific week for optimization
        defaultGameMinutes: 80,
        weights: { w_eml: 1.0, w_runs: 0.2, w_rest: 0.6 },
        wGlobal: 2.0,
        wRolling: 1.2,
        wRepeat: 1.0,
        wDispersion: 0.6,
        wLateFairness: 1.0,
        globalSlack: 1,
        rollingSlack: 0,
        maxPasses: 3,
        dryRun: false,  // Run with full validation to prevent +0d games
        // Ensure three-phase optimization runs
        optimize_days_since: true,  // Force days-since optimization
        force_full_validation: true  // Force full validation mode
      }
      
      console.log(`🎯 Auto-optimization API request for Week ${currentWeek}:`, requestBody)
      console.log(`🎯 Ensuring three-phase optimization with full validation...`)
      
      const response = await fetch('/api/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      })

      console.log('🔧 API response status:', response.status)

      if (!response.ok) {
        const errorText = await response.text()
        console.error('🔧 API error response:', errorText)
        throw new Error(`API error: ${response.status} - ${errorText}`)
      }

      const result = await response.json()
      console.log('🔧 Optimization result:', result)
      
      // Update optimization tracking
      console.log(`🎯 API result optimization tracking:`, {
        weeks_optimized: result.weeks_optimized,
        all_weeks_complete: result.all_weeks_complete,
        total_optimizable_weeks: result.total_optimizable_weeks
      })
      
      if (result.weeks_optimized) {
        setWeeksOptimized(result.weeks_optimized)
      }
      if (result.all_weeks_complete !== undefined) {
        setAllWeeksComplete(result.all_weeks_complete)
      }
      if (result.total_optimizable_weeks) {
        console.log(`🎯 Setting totalOptimizableWeeks to: ${result.total_optimizable_weeks}`)
        setTotalOptimizableWeeks(result.total_optimizable_weeks)
      } else {
        console.log(`🎯 WARNING: No total_optimizable_weeks in API result!`)
      }
      
      if (result.swaps && result.swaps.length > 0) {
        setOptimizationStats({ improvements: result.swaps.length })
        setOptimizationResults(result)
        
        // Check if this is a perfect solution (number of swaps equals total teams)
        if (result.swaps.length === teams.length) {
          console.log(`🎯 Perfect solution! ${result.swaps.length} changes = ${teams.length} teams`)
          
          // TEMPORARILY DISABLED: Auto-optimization to prevent 0-day gaps
          // Simple approach: just set flag to continue to next week
          /*
          if (currentWeek < totalOptimizableWeeks) {
            setShouldAutoOptimizeNext(true)
            console.log(`🎯 Week ${currentWeek} completed, will auto-optimize Week ${currentWeek + 1}`)
          } else {
            console.log(`🎯 Week ${currentWeek} is the last optimizable week. Auto-optimization complete!`)
            setAllWeeksComplete(true)
          }
          */
          console.log(`🎯 Auto-optimization DISABLED for testing. Week ${currentWeek} complete.`)
          console.log(`🎯 Please manually move to next week to test if this fixes the 0-day gap issue.`)
          
          // DEBUG: Ensure optimization results are still set for manual use
          if (result.swaps && result.swaps.length > 0) {
            console.log(`🎯 DEBUG: Setting optimization results for manual use: ${result.swaps.length} swaps`)
            setOptimizationResults(result)
            setOptimizationStats({ improvements: result.swaps.length })
          }
          
          // Update the schedule with optimization results
          if (result.schedule) {
            console.log(`🎯 Auto-optimization: Updating schedule for Week ${currentWeek}`)
            
            // Convert backend schedule to frontend format
            const newSchedule = result.schedule.map((game: any) => {
              const dateStr = game.start?.split('T')[0] || ''
              const startDate = new Date(game.start)
              const endDate = new Date(game.end)
              
              return {
                Date: dateStr,
                Start: startDate.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }),
                End: endDate.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }),
                Rink: game.rink || 'Unknown',
                Division: game.div || 'Unknown',
                HomeTeam: game.home || 'Unknown',
                AwayTeam: game.away || 'Unknown'
              }
            })
            
            // Update the schedule state
            setCurrentSchedule(newSchedule)
            // DON'T clear optimization results - keep them for manual implementation
            // setOptimizationResults(null)
            // setOptimizationStats(null)
            // DON'T mark as implemented - let user manually implement
            // setCurrentWeekImplemented(true)
            
            console.log(`🎯 Schedule updated successfully for Week ${currentWeek}`)
            console.log(`🎯 Optimization results preserved for manual implementation`)
          }
          
          // TEMPORARILY DISABLED: Auto-optimization to prevent 0-day gaps
          // Move to next week for auto-optimization
          /*
          if (currentWeek < totalOptimizableWeeks) {
            const nextWeek = currentWeek + 1
            setCurrentWeek(nextWeek)
            console.log(`🎯 Moving to Week ${nextWeek} for auto-optimization`)
          } else {
            console.log(`🎯 Week ${currentWeek} is the last optimizable week. Auto-optimization complete!`)
            setAllWeeksComplete(true)
          }
          */
          console.log(`🎯 Auto-optimization DISABLED for testing. Week ${currentWeek} complete.`)
          console.log(`🎯 Please manually move to next week to test if this fixes the 0-day gap issue.`)
          
          // DEBUG: Ensure optimization results are still set for manual use
          if (result.swaps && result.swaps.length > 0) {
            console.log(`🎯 DEBUG: Setting optimization results for manual use: ${result.swaps.length} swaps`)
            setOptimizationResults(result)
            setOptimizationStats({ improvements: result.swaps.length })
          }
        } else {
          // Don't automatically move to next week - let user control this
          console.log(`🎯 Week ${currentWeek} optimization complete. Waiting for user to implement changes.`)
        }
      } else {
        setOptimizationStats({ improvements: 0 })
        console.log(`🎯 Week ${currentWeek} optimization complete (no changes). Waiting for user to implement changes.`)
      }
    } catch (error) {
      console.error('❌ Optimization error:', error)
      setError('Optimization failed: ' + error.message)
    } finally {
      setIsOptimizing(false)
    }
  }

  const loadTeamsAndDivisions = async () => {
    if (!supabase) return

    try {
      // Load divisions
      const { data: divisionsData, error: divisionsError } = await supabase
        .from('divisions')
        .select('*')
        .eq('league_id', DEFAULT_LEAGUE_ID)
        .order('name', { ascending: true })

      if (divisionsError) throw divisionsError

      // Load teams
      const { data: teamsData, error: teamsError } = await supabase
        .from('teams')
        .select('*')
        .eq('league_id', DEFAULT_LEAGUE_ID)
        .order('name', { ascending: true })

      if (teamsError) throw teamsError

      // Map teams with division information
      const teamsWithDivisions = teamsData?.map(team => {
        const division = divisionsData?.find(div => div.id === team.division_id)
        return {
          ...team,
          division: division?.name || 'Unknown',
          divisionId: division?.id || team.division_id
        }
      }) || []

      setDivisions(divisionsData || [])
      setTeams(teamsWithDivisions || [])
      console.log('Loaded teams:', teamsWithDivisions?.length || 0)
      console.log('Loaded divisions:', divisionsData?.length || 0)
      console.log('Sample team with division:', teamsWithDivisions?.[0])
    } catch (error) {
      console.error('Error loading teams and divisions:', error)
    }
  }

  // Export functions
  const exportToCSV = () => {
    if (!currentSchedule.length) return
    
    // Create CSV content
    const headers = ['Game #', 'Date', 'Start Time', 'End Time', 'Rink', 'Division', 'Home Team', 'Away Team']
    const csvContent = [
      headers.join(','),
      ...currentSchedule.map((game, index) => [
        index + 1,
        game.Date,
        game.Start,
        game.End || '',
        game.Rink,
        game.Division,
        game.HomeTeam,
        game.AwayTeam
      ].join(','))
    ].join('\n')
    
    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute('download', `league-schedule-${new Date().toISOString().split('T')[0]}.csv`)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const exportToExcel = () => {
    if (!currentSchedule.length) return
    
    // Create Excel content using XLSX library
    const worksheet = currentSchedule.map((game, index) => ({
      'Game #': index + 1,
      'Date': game.Date,
      'Start Time': game.Start,
      'End Time': game.End || '',
      'Rink': game.Rink,
      'Division': game.Division,
      'Home Team': game.HomeTeam,
      'Away Team': game.AwayTeam
    }))
    
    // Import XLSX dynamically to avoid SSR issues
    import('xlsx').then((XLSX) => {
      const workbook = XLSX.utils.book_new()
      const ws = XLSX.utils.json_to_sheet(worksheet)
      
      // Set column widths
      const colWidths = [
        { wch: 8 },   // Game #
        { wch: 12 },  // Date
        { wch: 12 },  // Start Time
        { wch: 12 },  // End Time
        { wch: 15 },  // Rink
        { wch: 12 },  // Division
        { wch: 15 },  // Home Team
        { wch: 15 }   // Away Team
      ]
      ws['!cols'] = colWidths
      
      XLSX.utils.book_append_sheet(workbook, ws, 'League Schedule')
      
      // Generate and download file
      const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' })
      const blob = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      const link = document.createElement('a')
      const url = URL.createObjectURL(blob)
      link.setAttribute('href', url)
      link.setAttribute('download', `league-schedule-${new Date().toISOString().split('T')[0]}.xlsx`)
      link.style.visibility = 'hidden'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }).catch((error) => {
      console.error('Error exporting to Excel:', error)
      // Fallback to CSV if Excel export fails
      alert('Excel export failed. Falling back to CSV export.')
      exportToCSV()
    })
  }



  const generateSchedule = async () => {
    setIsGenerating(true)
    setError('')
    setSuccess('')

    try {
      console.log('🔍 DEBUG: Current state before request:')
      console.log('  - Slots count:', slots.length)
      console.log('  - Teams count:', teams.length)
      console.log('  - Divisions count:', divisions.length)
      console.log('  - Params:', params)
      console.log('  - Sample slot:', slots[0])
      console.log('  - Sample team:', teams[0])

      console.log('Sending request with:', {
        leagueId: DEFAULT_LEAGUE_ID,
        slotsCount: slots.length,
        teamsCount: teams.length,
        divisionsCount: divisions.length,
        params
      })

      const response = await fetch('/api/schedule', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          leagueId: DEFAULT_LEAGUE_ID,
          params,
          slots,
          teams,
          divisions
        }),
      })

      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.error || 'Failed to generate schedule')
      }

      // Debug: Log what we're getting
      console.log('Schedule generation result:', result)
      console.log('Schedule data:', result.schedule)

      // Set the schedule data from the response
      if (result.schedule && Array.isArray(result.schedule)) {
        // Ensure we have proper data structure
        let validSchedule = result.schedule.filter((game: any) => 
          game && typeof game === 'object' && game.Date && game.HomeTeam && game.AwayTeam
        )
        
        // Sort the schedule chronologically
        validSchedule = sortScheduleChronologically(validSchedule)
        
        console.log('Valid schedule entries:', validSchedule.length)
        console.log('📅 Schedule sorted chronologically from', validSchedule[0]?.Date, 'to', validSchedule[validSchedule.length - 1]?.Date)
        setCurrentSchedule(validSchedule)
        
        // Calculate total optimizable weeks (exclude week 1)
        const totalWeeks = Math.ceil(validSchedule.length / 10)
        const optimizableWeeks = totalWeeks - 1  // Week 1 doesn't need optimization
        setTotalOptimizableWeeks(optimizableWeeks)
        console.log(`📊 Schedule has ${totalWeeks} weeks, ${optimizableWeeks} can be optimized`)
        
        // Reset optimization state for new schedule
        setWeeksOptimized([])
        setAllWeeksComplete(false)
        setCurrentWeek(2)  // Start with Week 2
      } else {
        console.log('No valid schedule data received')
        setCurrentSchedule([])
        setTotalOptimizableWeeks(0)
        setWeeksOptimized([])
        setAllWeeksComplete(false)
      }

      setSuccess('Schedule generated successfully!')
      
    } catch (error) {
      console.error('Schedule generation error:', error)
      setError(error instanceof Error ? error.message : 'Failed to generate schedule')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleDaysSinceOptimization = async () => {
    if (!currentSchedule.length) return
    
    setIsDaysOptimizing(true)
    setError(null)
    
    try {
      console.log('🚀 Starting Days Since Last Played optimization...')
      console.log('📊 Schedule data:', currentSchedule.length, 'games')
      
      // Use the SAME reliable date calculation method as the team card!
      // This method works because it uses the original Date strings directly
      
      // Group games by week (bucket) - each bucket has 10 games
      const bucketSize = 10
      const buckets = []
      for (let i = 0; i < currentSchedule.length; i += bucketSize) {
        buckets.push(currentSchedule.slice(i, i + bucketSize))
      }
      
      console.log('📊 Bucket sizes:', buckets.map(b => b.length))
      
      // Start from bucket 2 (week 2) since bucket 1 (week 1) is already set
      let currentBucket = 1 // 0-indexed, so bucket 1 = week 2
      let totalChanges = 0
      
      while (currentBucket < buckets.length) {
        const bucket = buckets[currentBucket]
        if (!bucket || bucket.length === 0) break
        
        console.log(`🎯 Processing bucket ${currentBucket + 1} (week ${currentBucket + 1})`)
        console.log(`🎯 Initial bucket ${currentBucket + 1} state:`, bucket.map((game, idx) => 
          `Slot ${idx + 1}: ${game.HomeTeam} vs ${game.AwayTeam} at ${game.Date}`
        ))
        
        // Calculate days since last played for each team in this bucket
        // Use the SAME method as the team card: look at previous games in the schedule
        const teamDaysSince = new Map()
        
        bucket.forEach((game, gameIndex) => {
          if (!game.HomeTeam || !game.AwayTeam) return
          
          // For each team, find their last game in the schedule BEFORE this bucket
          const teams = [game.HomeTeam, game.AwayTeam]
          
          teams.forEach(team => {
            if (teamDaysSince.has(team)) return // Already calculated
            
            // Find the last game this team played before this bucket
            let lastGameDate = null
            let lastGameIndex = -1
            
            // Search backwards through the schedule to find the last game for this team
            for (let i = currentBucket * bucketSize - 1; i >= 0; i--) {
              const prevGame = currentSchedule[i]
              if (prevGame && prevGame.HomeTeam === team || prevGame.AwayTeam === team) {
                lastGameDate = prevGame.Date
                lastGameIndex = i
                break
              }
            }
            
            if (lastGameDate) {
              // Calculate days difference using the SAME method as team card
              const lastDate = new Date(lastGameDate)
              const currentDate = new Date(game.Date)
              const diffTime = currentDate.getTime() - lastDate.getTime()
              const daysSince = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
              
              teamDaysSince.set(team, daysSince)
              console.log(`🎯 ${team}: ${daysSince} days since last played (last: ${lastGameDate}, current: ${game.Date})`)
            } else {
              // Team hasn't played yet
              teamDaysSince.set(team, 999)
              console.log(`🎯 ${team}: Never played before (999 days priority)`)
            }
          })
        })
        
        // Sort teams by days since last played (longest first = highest priority)
        const teamsByPriority = Array.from(teamDaysSince.entries())
          .sort(([, daysA], [, daysB]) => daysB - daysA)
        
        console.log(`🎯 Teams by priority (longest days first):`, teamsByPriority.slice(0, 5))
        
        // Now optimize the bucket by placing teams with longest gaps in earliest slots
        // But ONLY if the slot doesn't have a late game (after 10:31 PM)
        const lateThreshold = new Date('2000-01-01T22:31:00') // 10:31 PM
        
        let bucketChanges = 0
        const processedTeams = new Set()
        
        // Process teams by priority
        for (const [team, daysSince] of teamsByPriority) {
          if (processedTeams.has(team)) continue
          
          // Find the matchup this team belongs to
          const teamMatchup = bucket.find(game => 
            game.HomeTeam === team || game.AwayTeam === team
          )
          
          if (!teamMatchup) continue
          
          const opponent = teamMatchup.HomeTeam === team ? teamMatchup.AwayTeam : teamMatchup.HomeTeam
          if (processedTeams.has(opponent)) continue
          
          // Find the earliest available slot that's not a late game
          let bestSlot = -1
          let bestSlotTime = null
          
          for (let slotIdx = 0; slotIdx < bucket.length; slotIdx++) {
            const slotGame = bucket[slotIdx]
            
            // Skip if this slot already has teams
            if (slotGame.HomeTeam && slotGame.AwayTeam) continue
            
            // Check if this would be a late game
            const slotTime = new Date(`${slotGame.Date}T${slotGame.Start}`)
            if (slotTime >= lateThreshold) {
              console.log(`🎯 Slot ${slotIdx + 1}: ${slotGame.Date} ${slotGame.Start} is LATE (cannot be moved)`)
              continue
            }
            
            // This slot is available and not late
            if (bestSlot === -1 || slotTime < bestSlotTime) {
              bestSlot = slotIdx
              bestSlotTime = slotTime
            }
          }
          
          if (bestSlot !== -1) {
            // Place the matchup in the best slot
            const originalSlot = bucket.findIndex(game => 
              game.HomeTeam === team || game.AwayTeam === team
            )
            
            if (originalSlot !== -1 && originalSlot !== bestSlot) {
              // Swap the matchups
              [bucket[originalSlot], bucket[bestSlot]] = [bucket[bestSlot], bucket[originalSlot]]
              console.log(`🎯 SWAPPED: ${team} vs ${opponent} moved from slot ${originalSlot + 1} to slot ${bestSlot + 1}`)
              bucketChanges++
            }
            
            // Mark both teams as processed
            processedTeams.add(team)
            processedTeams.add(opponent)
          }
        }
        
        console.log(`🎯 Bucket ${currentBucket + 1}: Made ${bucketChanges} changes`)
        totalChanges += bucketChanges
        
        // Move to next bucket
        currentBucket++
        
        // Update the button text to show progress
        setCurrentDaysOptimizeWeek(currentBucket + 1)
      }
      
      console.log(`✅ Days optimization completed successfully!`)
      console.log(`📊 Total changes made: ${totalChanges}`)
      
      // Update the schedule with the optimized buckets
      const newSchedule = buckets.flat()
      setCurrentSchedule(newSchedule)
      
      setDaysOptimizeComplete(true)
      setCurrentDaysOptimizeWeek(null)
      
    } catch (error) {
      console.error('❌ Days optimization error:', error)
      setError('Days optimization failed: ' + error.message)
    } finally {
      setIsDaysOptimizing(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Calendar className="w-6 h-6" />
          Schedule Generation
        </h2>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gray-800 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold">Data Imported</h3>
              <p className="text-2xl font-bold text-green-400">{slots.length}</p>
              <p className="text-sm text-gray-400">Available time slots</p>
            </div>
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold">Teams Configured</h3>
              <p className="text-2xl font-bold text-green-400">{teams.length}</p>
              <p className="text-sm text-gray-400">Teams across {divisions.length} divisions</p>
            </div>
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6">
          <button
            onClick={generateSchedule}
            disabled={isGenerating || slots.length === 0 || teams.length === 0}
            className="w-full h-full bg-green-600 hover:bg-green-700 disabled:bg-gray-600 px-6 py-3 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors"
          >
            {isGenerating ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Calendar className="w-5 h-5" />
                Generate Schedule
            </>
            )}
          </button>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-400">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-900/20 border border-green-800 rounded-lg p-4 text-green-400">
          {success}
        </div>
      )}

      {/* Game Counter */}
      {currentSchedule.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Game Count Summary</h3>
          
          {/* Total Games */}
          <div className="mb-4">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Games Generated:</span>
              <span className="text-2xl font-bold text-green-400">
                {currentSchedule.length}/{Math.round((teams.length * params.gamesPerTeam) / 2)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Status:</span>
              <span className={`text-sm font-medium px-2 py-1 rounded ${
                currentSchedule.length === Math.round((teams.length * params.gamesPerTeam) / 2)
                  ? 'bg-green-900/20 text-green-400 border border-green-800' 
                  : 'bg-yellow-900/20 text-yellow-400 border border-yellow-800'
              }`}>
                {currentSchedule.length === Math.round((teams.length * params.gamesPerTeam) / 2) ? '✅ Complete' : '⚠️ Incomplete'}
              </span>
            </div>
            
            {/* Optimization Controls */}
            <div className="mt-4 flex items-center gap-3">
              {allWeeksComplete ? (
                // All weeks optimized - show completion state and Days Since Optimization button
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white font-medium rounded-lg">
                    <CheckCircle className="w-4 h-4" />
                    🎯 All Weeks Optimized
                  </div>
                  
                    
                </div>
              ) : (
                // Still optimizing - show current week button
                <>
                  {allWeeksComplete ? (
                    // All weeks optimized - show completion state
                    <div className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white font-medium rounded-lg">
                      <CheckCircle className="w-4 h-4" />
                      🎯 All Weeks Optimized
                    </div>
                  ) : (
                    // Still optimizing - show current week button
                    <button
                      onClick={handleOptimizeSchedule}
                      disabled={isOptimizing}
                      className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-all duration-200 shadow-lg hover:shadow-xl"
                    >
                      <Zap className="w-4 h-4" />
                      {isOptimizing ? 'Optimizing...' : `Optimize Week ${currentWeek}`}
                    </button>
                  )}
                  
                  {optimizationStats && (
                    <div className="flex items-center gap-3">
                      {optimizationResults && (
                        <div className="flex items-center gap-2">
                          {currentWeekImplemented ? (
                            // Button is disabled and shows "Implemented"
                            <button
                              disabled
                              className="flex items-center gap-2 px-4 py-2 bg-gray-500 text-gray-300 font-medium rounded-lg cursor-not-allowed transition-all duration-200 shadow-lg"
                            >
                              Implemented
                            </button>
                          ) : (
                            // Button is active and can be clicked
                            <button
                              onClick={() => {
                              if (optimizationResults.schedule) {
                                // Convert the optimized schedule back to the frontend format
                                let newSchedule = optimizationResults.schedule.map((game: any) => {
                                  // IMPORTANT: Extract date directly from the original string to avoid timezone issues
                                  let dateStr = ''
                                  if (game.start && typeof game.start === 'string') {
                                    if (game.start.includes('T')) {
                                      // ISO format: "2025-09-05T21:00:00" -> extract "2025-09-05"
                                      dateStr = game.start.split('T')[0]
                                    } else {
                                      // Fallback: try to parse as Date
                                      const startDate = new Date(game.start)
                                      if (!isNaN(startDate.getTime())) {
                                        dateStr = startDate.toISOString().split('T')[0]
                                      }
                                    }
                                  }
                                  
                                  // Parse the start and end times for display formatting only
                                  const startDate = new Date(game.start)
                                  const endDate = new Date(game.end)
                                  
                                  // Format time as 12-hour format
                                  const startTime = startDate.toLocaleTimeString('en-US', { 
                                    hour: 'numeric', 
                                    minute: '2-digit',
                                    hour12: true
                                  })
                                  
                                  const endTime = endDate.toLocaleTimeString('en-US', { 
                                    hour: 'numeric', 
                                    minute: '2-digit',
                                    hour12: true
                                  })
                                  
                                  // Find the actual team names from the teams array
                                  const findTeamName = (teamId: string) => {
                                    // First try to find by exact name match
                                    const exactMatch = teams.find(t => t.name === teamId)
                                    if (exactMatch) return exactMatch.name
                                    
                                    // If no exact match, try to find by stripping prefixes
                                    const strippedId = teamId.replace(/^(Team |b)/, '')
                                    const strippedMatch = teams.find(t => t.name === strippedId || t.name === `b${strippedId}` || t.name === `Team ${strippedId}`)
                                    if (strippedMatch) return strippedMatch.name
                                    
                                    // Fallback to original ID if no match found
                                    console.warn(`⚠️ Could not find team name for ID: ${teamId}`)
                                    return teamId
                                  }
                                  
                                  const homeTeam = findTeamName(game.home)
                                  const awayTeam = findTeamName(game.away)
                                  
                                  // Debug: Log date and time processing
                                  console.log(`🔧 Date/Time processing:`, {
                                    originalStart: game.start,
                                    extractedDate: dateStr,
                                    formattedStart: startTime,
                                    formattedEnd: endTime
                                  })
                                  
                                  // Debug: Log team name conversion
                                  console.log(`🔧 Team name conversion: ${game.home} → ${homeTeam}, ${game.away} → ${awayTeam}`)
                                  
                                  return {
                                    Date: dateStr,
                                    Start: startTime,
                                    End: endTime,
                                    Rink: game.rink || 'Unknown',
                                    Division: game.div || 'Unknown',
                                    HomeTeam: homeTeam,
                                    AwayTeam: awayTeam
                                  }
                                })
                                
                                // Sort the optimized schedule chronologically
                                newSchedule = sortScheduleChronologically(newSchedule)
                                
                                console.log('🔧 Applying optimized schedule:', {
                                  originalCount: currentSchedule.length,
                                  newCount: newSchedule.length,
                                  sampleOriginal: currentSchedule[0],
                                  sampleNew: newSchedule[0]
                                })
                                
                                // Validate the converted schedule
                                if (newSchedule.length === 0) {
                                  console.error('❌ Converted schedule is empty!')
                                  setError('Failed to convert optimized schedule')
                                  return
                                }
                                
                                if (!newSchedule[0].Date || !newSchedule[0].Start) {
                                  console.error('❌ Converted schedule has missing fields:', newSchedule[0])
                                  setError('Converted schedule has invalid format')
                                  return
                                }
                                
                                console.log('✅ Schedule conversion successful, updating state...')
                                setCurrentSchedule(newSchedule)
                                setSuccess('✅ Schedule updated with optimization results!')
                                
                                // Debug: Log the new schedule structure
                                console.log('🔍 New schedule structure:', {
                                  totalGames: newSchedule.length,
                                  sampleGames: newSchedule.slice(0, 3),
                                  teamNames: Array.from(new Set([
                                    ...newSchedule.map(g => g.HomeTeam),
                                    ...newSchedule.map(g => g.AwayTeam)
                                  ]))
                                })
                                
                                // Mark current week as implemented
                                setCurrentWeekImplemented(true)
                                
                                // Update optimization progress after applying changes
                                if (weeksOptimized.length > 0 && !weeksOptimized.includes(currentWeek - 1)) {
                                  const updatedWeeks = [...weeksOptimized, currentWeek - 1]
                                  setWeeksOptimized(updatedWeeks)
                                  
                                  // Check if all weeks are now complete
                                  if (updatedWeeks.length >= totalOptimizableWeeks) {
                                    setAllWeeksComplete(true)
                                    console.log('🎯 All weeks have been optimized!')
                                  }
                                }
                                
                                // Also check if we've reached the last week
                                if (currentWeek >= totalOptimizableWeeks + 1) {
                                  setAllWeeksComplete(true)
                                  console.log('🎯 Reached last week. All weeks complete!')
                                } else {
                                  // Move to next week only after implementing changes
                                  const nextWeek = currentWeek + 1
                                  setCurrentWeek(nextWeek)
                                  console.log(`🎯 Changes implemented. Moving to Week ${nextWeek}`)
                                }
                              } else {
                                console.error('❌ No schedule data found in optimization results:', {
                                  hasSchedule: !!optimizationResults.schedule,
                                  scheduleType: typeof optimizationResults.schedule,
                                  isArray: Array.isArray(optimizationResults.schedule),
                                  availableKeys: Object.keys(optimizationResults)
                                })
                                setError('No schedule data found in optimization results')
                              }
                            }}
                            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition-all duration-200 shadow-lg hover:shadow-xl"
                          >
                            Implement {optimizationStats.improvements} changes
                          </button>
                          )}
                          <button
                            onClick={() => {
                              // Just show the modal, don't apply changes
                              setShowOptimizationModal(true)
                            }}
                            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-all duration-200 shadow-lg hover:shadow-xl"
                          >
                            View Changes
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                  

                </>
              )}
            </div>
          </div>

          {/* Per-Team Breakdown */}
          <div>
            <div className="mb-3">
              <h4 className="text-md font-medium text-gray-300">Games per Team:</h4>
            </div>
            

            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {teams.map((team) => {
                // Enhanced team name matching to handle different naming conventions
                const teamGames = currentSchedule.filter(game => {
                  const homeTeam = game.HomeTeam || ''
                  const awayTeam = game.AwayTeam || ''
                  
                  // Direct name match (highest priority)
                  if (homeTeam === team.name || awayTeam === team.name) {
                    return true
                  }
                  
                            // Handle division-based naming - only if no direct match found
          if (team.division === 'Tin South' && team.name.startsWith('b')) {
            const teamNumber = team.name.replace('b', '')
            if (homeTeam === teamNumber || awayTeam === teamNumber) {
              return true
            }
          }
                  
                  // Handle "Team X" format - only if no direct match found
                  if (team.name.startsWith('Team ')) {
                    const teamNumber = team.name.replace('Team ', '')
                    if (homeTeam === teamNumber || awayTeam === teamNumber) {
                      return true
                    }
                  }
                  
                  return false
                }).length
                
                const isComplete = teamGames === params.gamesPerTeam
                
                // Debug logging for team name matching
                if (teamGames === 0) {
                  console.log(`🔍 Team ${team.name} (${team.division}) - No games found. Sample schedule entries:`, 
                    currentSchedule.slice(0, 3).map(g => ({ home: g.HomeTeam, away: g.AwayTeam }))
                  )
                } else if (teamGames > params.gamesPerTeam) {
                  console.log(`⚠️ Team ${team.name} (${team.division}) - Found ${teamGames} games (expected ${params.gamesPerTeam}). This suggests double-counting.`)
                }
                
                return (
                  <div key={team.id} className="bg-gray-700 rounded p-3">
                    <div className="flex items-center justify-between mb-1">
                      <div>
                        <span className="text-sm font-medium text-gray-300">{team.name}</span>
                        <span className="text-xs text-gray-500 ml-2">-{team.division}</span>
                      </div>
                      <span className={`text-xs px-1 py-0.5 rounded ${
                        isComplete 
                          ? 'bg-green-900/20 text-green-400' 
                          : 'bg-yellow-900/20 text-yellow-400'
                      }`}>
                        {isComplete ? '✓' : '!'}
                      </span>
                    </div>
                    <div
                      className="text-lg font-bold text-blue-400 cursor-pointer hover:text-blue-300 transition-colors"
                      onClick={() => handleTeamClick(team.name)}
                      title={`Click to view ${team.name}'s schedule`}
                    >
                      {teamGames}/{params.gamesPerTeam}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Current Schedule Display */}
      {currentSchedule.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">Generated Schedule</h3>
            {scheduleUrl && (
              <a
                href={scheduleUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-green-600 hover:bg-green-700 px-3 py-1 rounded text-sm font-medium flex items-center gap-1 transition-colors"
              >
                <Download className="w-4 h-4" />
                Download Full Schedule
              </a>
            )}
          </div>
          
          {/* Schedule Table */}
          {/* Schedule Table with Bucket Highlighting */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left py-2 px-3 text-gray-400">#</th>
                  <th className="text-left py-2 px-3">Date</th>
                  <th className="text-left py-2 px-3">Start</th>
                  <th className="text-left py-2 px-3">Rink</th>
                  <th className="text-left py-2 px-3">Division</th>
                  <th className="text-left py-2 px-3">Home Team</th>
                  <th className="text-left py-2 px-3">Away Team</th>
                  <th className="text-left py-2 px-3 text-gray-400">Bucket</th>
                </tr>
              </thead>
              <tbody>
                {currentSchedule.map((game, index) => {
                  const bucketNumber = Math.floor(index / 10) + 1
                  const isEvenBucket = bucketNumber % 2 === 0
                  
                  return (
                    <tr 
                      key={index} 
                      className={`border-b border-gray-700 hover:bg-gray-700 transition-colors ${
                        isEvenBucket ? 'bg-gray-800/50' : 'bg-gray-900/50'
                      }`}
                    >
                      <td className="py-2 px-3 text-gray-400 font-mono">{index + 1}</td>
                      <td className="py-2 px-3">{game.Date}</td>
                      <td className="py-2 px-3">{game.Start}</td>
                      <td className="py-2 px-3">{game.Rink}</td>
                      <td className="py-2 px-3">{game.Division}</td>
                      <td className="py-2 px-3 font-medium">{game.HomeTeam}</td>
                      <td className="py-2 px-3 font-medium">{game.AwayTeam}</td>
                      <td className="py-2 px-3 text-gray-400 font-mono">{bucketNumber}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Export Buttons */}
                  {currentSchedule.length > 0 && (
          <div className="mt-6 pt-6 border-t border-gray-700">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-lg font-medium text-gray-300 mb-2">Export Schedule</h4>
                <p className="text-sm text-gray-400">
                  Download your schedule in CSV or Excel format for external use
                </p>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => exportToCSV()}
                  className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors"
                >
                  <Download className="w-4 h-4" />
                  Export CSV
                </button>
                <button
                  onClick={() => exportToExcel()}
                  className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors"
                >
                  <Download className="w-4 h-4" />
                  Export Excel
                </button>
              </div>
            </div>
          </div>
        )}







        </div>
      )}

      {/* Team Schedule Modal */}
      {showTeamSchedule && selectedTeam && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          onKeyDown={(e) => {
            if (e.key === 'ArrowLeft') {
              const currentIndex = teams.findIndex(t => t.name === selectedTeam)
              const prevIndex = currentIndex > 0 ? currentIndex - 1 : teams.length - 1
              setSelectedTeam(teams[prevIndex].name)
            } else if (e.key === 'ArrowRight') {
              const currentIndex = teams.findIndex(t => t.name === selectedTeam)
              const nextIndex = currentIndex < teams.length - 1 ? currentIndex + 1 : 0
              setSelectedTeam(teams[nextIndex].name)
            } else if (e.key === 'Escape') {
              closeTeamSchedule()
            }
          }}
          tabIndex={0}
        >
          <div className="bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-700">
              <div className="flex items-center gap-4">
                {/* Previous Team Arrow */}
                <button
                  onClick={() => {
                    const currentIndex = teams.findIndex(t => t.name === selectedTeam)
                    const prevIndex = currentIndex > 0 ? currentIndex - 1 : teams.length - 1
                    setSelectedTeam(teams[prevIndex].name)
                  }}
                  className="text-gray-400 hover:text-white transition-colors p-2 rounded-lg hover:bg-gray-700"
                  title="Previous Team"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                </button>
                
                <h3 className="text-xl font-semibold text-white">
                  {selectedTeam}'s Schedule
                  <span className="text-sm text-gray-400 ml-2">
                    ({teams.findIndex(t => t.name === selectedTeam) + 1} of {teams.length})
                  </span>
                </h3>
                
                {/* Next Team Arrow */}
                <button
                  onClick={() => {
                    const currentIndex = teams.findIndex(t => t.name === selectedTeam)
                    const nextIndex = currentIndex < teams.length - 1 ? currentIndex + 1 : 0
                    setSelectedTeam(teams[nextIndex].name)
                  }}
                  className="text-gray-400 hover:text-white transition-colors p-2 rounded-lg hover:bg-gray-700"
                  title="Next Team"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>
              
              <button
                onClick={closeTeamSchedule}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
              {(() => {
                const teamGames = currentSchedule.filter(
                  game => game.HomeTeam === selectedTeam || game.AwayTeam === selectedTeam
                ).sort((a, b) => new Date(a.Date).getTime() - new Date(b.Date).getTime())
                
                if (teamGames.length === 0) {
                  return (
                    <div className="text-center py-8">
                      <p className="text-gray-400">No games scheduled for {selectedTeam}</p>
                    </div>
                  )
                }

                return (
                  <div className="space-y-4">
                                         {/* EML Distribution Summary */}
                     <div className="bg-gray-700 rounded-lg p-4">
                       <div className="text-sm text-gray-400 mb-2">EML Distribution:</div>
                       <div className="grid grid-cols-4 gap-4 text-sm">
                         <div>
                           <span className="text-gray-400">Early:</span>
                           <div className="text-lg font-bold text-yellow-400">
                             {teamGames.filter(game => getEMLCategory(game.Start) === 'Early').length}
                           </div>
                         </div>
                         <div>
                           <span className="text-gray-400">Mid:</span>
                           <div className="text-lg font-bold text-orange-400">
                             {teamGames.filter(game => getEMLCategory(game.Start) === 'Mid').length}
                           </div>
                         </div>
                         <div>
                           <span className="text-gray-400">Late:</span>
                           <div className="text-lg font-bold text-red-400">
                             {teamGames.filter(game => getEMLCategory(game.Start) === 'Late').length}
                           </div>
                         </div>
                         <div>
                           <span className="text-gray-400">Avg Days:</span>
                           <div className="text-lg font-bold text-blue-400">
                             {(() => {
                               // Calculate average days between games
                               if (teamGames.length <= 1) return '—'
                               
                               let totalDays = 0
                               let validIntervals = 0

                               
                               for (let i = 1; i < teamGames.length; i++) {
                                 const lastGameDate = new Date(teamGames[i - 1].Date)
                                 const currentGameDate = new Date(teamGames[i].Date)
                                 const diffTime = currentGameDate.getTime() - lastGameDate.getTime()
                                 const daysDiff = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
                                 

                                 
                                 if (daysDiff > 0) { // Only count valid intervals
                                   totalDays += daysDiff
                                   validIntervals++
                                 }
                               }
                               

                               
                               if (validIntervals === 0) return '—'
                               // Use total games for average spacing per game (not per interval)
                               return (totalDays / teamGames.length).toFixed(1)
                             })()}
                           </div>
                         </div>
                       </div>
                       {/* Debug: Show actual EML values */}
                       <div className="mt-2 text-xs text-gray-500">
                         Debug EML values: {(() => {
                           // Use earlyStart/midStart from params (now using START times)
                           const earlyStart = params.eml?.earlyStart || '22:01'
                           const midStart = params.eml?.midStart || '22:31'
                           // Convert 24-hour to 12-hour for display
                           const formatTime = (time24: string) => {
                             const match = time24.match(/^(\d{1,2}):(\d{2})$/)
                             if (!match) return time24
                             let hours = parseInt(match[1])
                             const minutes = match[2]
                             const ampm = hours >= 12 ? 'PM' : 'AM'
                             if (hours > 12) hours -= 12
                             if (hours === 0) hours = 12
                             return `${hours}:${minutes} ${ampm}`
                           }
                           return `Thresholds (START times): Early < ${formatTime(earlyStart)}, Mid < ${formatTime(midStart)}`
                         })()}
                       </div>
                     </div>

                    {/* Games List */}
                    <div className="space-y-2">
                      <h4 className="text-lg font-medium text-gray-300">Game Details:</h4>
                      {teamGames.map((game, index) => {
                        // Calculate days since last played (for games after the first)
                        let daysSinceLast = null
                        if (index > 0) {
                          const lastGameDate = new Date(teamGames[index - 1].Date)
                          const currentGameDate = new Date(game.Date)
                          const diffTime = currentGameDate.getTime() - lastGameDate.getTime()
                          daysSinceLast = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
                        }

                        // Check if this is a repeat matchup (2nd time playing the same opponent)
                        const opponent = game.HomeTeam === selectedTeam ? game.AwayTeam : game.HomeTeam
                        const previousGames = teamGames.slice(0, index)
                        const isRepeatMatchup = previousGames.some(prevGame => {
                          const prevOpponent = prevGame.HomeTeam === selectedTeam ? prevGame.AwayTeam : prevGame.HomeTeam
                          return prevOpponent === opponent
                        })

                        return (
                          <div key={index} className="bg-gray-700 rounded-lg p-3">
                            <div className="flex items-center justify-between text-sm">
                              <div className="flex items-center gap-3 flex-1">
                                <span className="text-gray-400 w-8">#{index + 1}</span>
                                <span className={`px-2 py-1 rounded text-xs font-medium ${
                                  game.HomeTeam === selectedTeam 
                                    ? 'bg-green-900/20 text-green-400' 
                                    : 'bg-red-900/20 text-red-400'
                                }`}>
                                  {game.HomeTeam === selectedTeam ? 'HOME' : 'AWAY'}
                                </span>
                                <span className="text-gray-300 font-medium">
                                  {game.HomeTeam === selectedTeam ? game.AwayTeam : game.HomeTeam}
                                </span>
                                {/* Repeat matchup indicator */}
                                {isRepeatMatchup && (
                                  <span className="px-2 py-1 rounded text-xs font-medium bg-purple-900/20 text-purple-400 border border-purple-500/30">
                                    2nd
                                  </span>
                                )}
                              </div>
                              
                              <div className="flex items-center gap-4 text-gray-300">
                                <span className="w-24 text-xs">{game.Date}</span>
                                <span className="w-20 whitespace-nowrap">
                                  {/* Use the formatted Start time from currentSchedule */}
                                  {game.Start || 'Unknown'}
                                </span>
                                <span className="w-24">{game.Rink}</span>
                                <span className={`font-medium w-16 ${
                                  daysSinceLast === 0 ? 'text-red-400' : 'text-blue-400'
                                }`}>
                                  {daysSinceLast !== null ? `+${daysSinceLast}d` : '—'}
                                </span>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              })()}
            </div>
          </div>
        </div>
      )}
      
      {/* Optimization Results Modal */}
      {showOptimizationModal && optimizationResults && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-lg max-w-6xl w-full max-h-[90vh] overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-700">
              <h3 className="text-xl font-semibold text-white">
                Optimization Results
              </h3>
              <button
                onClick={() => setShowOptimizationModal(false)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
              {/* Summary */}
              <div className="mb-6">
                <h4 className="text-lg font-medium text-gray-300 mb-3">Summary</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-gray-700 rounded-lg p-3">
                    <div className="text-sm text-gray-400">Total Changes</div>
                    <div className="text-2xl font-bold text-blue-400">
                      {optimizationResults.improvement || 0}
                    </div>
                  </div>
                  {optimizationResults.score_before && optimizationResults.score_after && (
                    <>
                      <div className="bg-gray-700 rounded-lg p-3">
                        <div className="text-sm text-gray-400">Division A Score</div>
                        <div className="text-lg font-bold text-green-400">
                          {optimizationResults.score_before.a?.toFixed(2) || 'N/A'} → {optimizationResults.score_after.a?.toFixed(2) || 'N/A'}
                        </div>
                      </div>
                      <div className="bg-gray-700 rounded-lg p-3">
                        <div className="text-sm text-gray-400">Division B Score</div>
                        <div className="text-lg font-bold text-green-400">
                          {optimizationResults.score_before.b?.toFixed(2) || 'N/A'} → {optimizationResults.score_after.b?.toFixed(2) || 'N/A'}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Swaps List */}
              {optimizationResults.swaps && optimizationResults.swaps.length > 0 && (
                <div className="mb-6">
                  <h4 className="text-lg font-medium text-gray-300 mb-3">
                    Proposed Swaps ({optimizationResults.swaps.length} changes)
                  </h4>
                  <p className="text-sm text-gray-400 mb-3">
                    Each entry shows the optimization phase, matchup details, date, time, and rink information.
                  </p>
                  





                  
                  <div className="space-y-2">
                    {optimizationResults.swaps
                      .filter((swap: any) => {
                        // Hide Game Clearing cards (Phase 0 or division === 'cleared')
                        if (swap.phase && swap.phase.includes('Phase 0')) return false;
                        if (swap.division === 'cleared') return false;
                        return true;
                      })
                      .map((swap: any, index: number) => {
                      // Determine the phase and color for this swap
                      let phaseInfo = null;
                      let phaseColor = 'text-gray-400';
                      let phaseBg = 'bg-gray-700';
                      
                      if (swap.phase) {
                        if (swap.phase.includes('Phase 1') || swap.phase.includes('Late Game')) {
                          phaseInfo = 'Late Game Consistency';
                          phaseColor = 'text-blue-400';
                          phaseBg = 'bg-blue-900/20 border border-blue-800';
                        } else if (swap.phase.includes('Phase 2') && !swap.phase.includes('Conflict Resolution')) {
                          phaseInfo = 'Days Since Last Game';
                          phaseColor = 'text-green-400';
                          phaseBg = 'bg-green-900/20 border border-green-800';
                        } else if (swap.phase.includes('Conflict Resolution')) {
                          phaseInfo = 'Conflict Resolution';
                          phaseColor = 'text-orange-400';
                          phaseBg = 'bg-orange-900/20 border border-orange-800';
                        }
                      } else if (swap.was_late) {
                        phaseInfo = 'Late Game Consistency';
                        phaseColor = 'text-blue-400';
                        phaseBg = 'bg-blue-900/20 border border-blue-800';
                      }
                      
                      return (
                        <div key={index} className={`${phaseBg} rounded-lg p-3`}>
                          <div className="flex items-center justify-between">
                            <div className="flex-1">
                              {/* Phase indicator */}
                              {phaseInfo && (
                                <div className="mb-2">
                                  <span className={`text-xs font-medium px-2 py-1 rounded-full ${phaseColor} bg-opacity-20`}>
                                    {phaseInfo}
                                  </span>
                                </div>
                              )}
                              
                              <div className="flex items-center">
                                {/* Show game ID if available */}
                                {swap.game_id !== undefined && (
                                  <>
                                    <span className="text-blue-400 font-medium">Game {swap.game_id}</span>
                                    <span className="text-gray-400 mx-2">•</span>
                                  </>
                                )}
                                
                                {/* Show division if available */}
                                {swap.division && swap.division !== 'cleared' && (
                                  <>
                                    <span className="text-purple-400 font-medium">{swap.division.toUpperCase()}</span>
                                    <span className="text-gray-400 mx-2">•</span>
                                  </>
                                )}
                                
                                {/* Show the actual team swap */}
                                {swap.original_home && swap.original_away && swap.new_home && swap.new_away ? (
                                  <span className="text-gray-300">
                                    <span className="text-red-400">{swap.original_home}</span> vs <span className="text-blue-400">{swap.original_away}</span>
                                    <span className="text-gray-400 mx-2">→</span>
                                    <span className="text-green-400">{swap.new_home}</span> vs <span className="text-yellow-400">{swap.new_away}</span>
                                  </span>
                                ) : swap.note ? (
                                  <span className="text-gray-300">{swap.note}</span>
                                ) : swap.after && swap.after.includes(' vs ') ? (
                                  <span className="text-gray-300">
                                    {swap.after.replace(/\([^)]+\)/g, '').trim()}
                                  </span>
                                ) : (
                                  <span className="text-gray-300">Team assignment change</span>
                                )}
                              </div>
                              
                              {/* Show additional details if available */}
                              {swap.original_home && swap.original_away && swap.new_home && swap.new_away && (
                                <div className="text-sm text-gray-400 mt-2">
                                  <span className="text-red-400">Before:</span> {swap.original_home} (home) vs {swap.original_away} (away)
                                  <br />
                                  <span className="text-green-400">After:</span> {swap.new_home} (home) vs {swap.new_away} (away)
                                </div>
                              )}
                              
                              {/* Show date, time, and rink information if available */}
                              {(swap.date || swap.rink || swap.time) && (
                                <div className="text-sm text-gray-400 mt-2">
                                  {swap.date && (
                                    <div className="flex items-center gap-2">
                                      <span className="text-cyan-400">📅</span>
                                      <span className="text-gray-300">{new Date(swap.date).toLocaleDateString('en-US', { 
                                        weekday: 'short',
                                        month: 'short', 
                                        day: 'numeric',
                                        year: 'numeric'
                                      })}</span>
                                      {swap.time && (
                                        <span className="text-gray-400 mx-2">•</span>
                                      )}
                                      {swap.time && (
                                        <span className="text-gray-300">
                                          {new Date(swap.time).toLocaleTimeString('en-US', { 
                                            hour: 'numeric', 
                                            minute: '2-digit',
                                            hour12: true 
                                          })}
                                        </span>
                                      )}
                                      {swap.rink && (
                                        <span className="text-gray-400 mx-2">•</span>
                                      )}
                                      {swap.rink && (
                                        <span className="text-gray-300">
                                          <span className="text-cyan-400">🏒</span> {swap.rink}
                                        </span>
                                      )}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                            

                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Buckets Analysis */}
              {optimizationResults.buckets && (
                <div>
                  <h4 className="text-lg font-medium text-gray-300 mb-3">EML Distribution Analysis</h4>
                  {Object.entries(optimizationResults.buckets).map(([division, teams]) => (
                    <div key={division} className="mb-4">
                      <h5 className="text-md font-medium text-gray-400 mb-2">Division {division.toUpperCase()}</h5>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-gray-700">
                              <th className="text-left py-2 px-3 text-gray-400">Team</th>
                              <th className="text-center py-2 px-3 text-gray-400">E</th>
                              <th className="text-center py-2 px-3 text-gray-400">M</th>
                              <th className="text-center py-2 px-3 text-gray-400">L</th>
                              <th className="text-center py-2 px-3 text-gray-400">Target E</th>
                              <th className="text-center py-2 px-3 text-gray-400">Target M</th>
                              <th className="text-center py-2 px-3 text-gray-400">Target L</th>
                              <th className="text-center py-2 px-3 text-gray-400">ΔE</th>
                              <th className="text-center py-2 px-3 text-gray-400">ΔM</th>
                              <th className="text-center py-2 px-3 text-gray-400">ΔL</th>
                              <th className="text-center py-2 px-3 text-gray-400">B2B</th>
                              <th className="text-center py-2 px-3 text-gray-400">Long Gaps</th>
                              <th className="text-center py-2 px-3 text-gray-400">Avg Gap</th>
                            </tr>
                          </thead>
                          <tbody>
                            {teams.map((team: any, index: number) => (
                              <tr key={index} className="border-b border-gray-700 hover:bg-gray-700">
                                <td className="py-2 px-3 text-gray-300 font-medium">{team.Team}</td>
                                <td className="py-2 px-3 text-center text-yellow-400">{team.E}</td>
                                <td className="py-2 px-3 text-center text-orange-400">{team.M}</td>
                                <td className="py-2 px-3 text-center text-red-400">{team.L}</td>
                                <td className="py-2 px-3 text-center text-gray-400">{team['Target E']}</td>
                                <td className="py-2 px-3 text-center text-gray-400">{team['Target M']}</td>
                                <td className="py-2 px-3 text-center text-gray-400">{team['Target L']}</td>
                                <td className={`py-2 px-3 text-center ${team.ΔE > 0 ? 'text-red-400' : team.ΔE < 0 ? 'text-green-400' : 'text-gray-400'}`}>
                                  {team.ΔE > 0 ? '+' : ''}{team.ΔE}
                                </td>
                                <td className={`py-2 px-3 text-center ${team.ΔM > 0 ? 'text-red-400' : team.ΔM < 0 ? 'text-green-400' : 'text-gray-400'}`}>
                                  {team.ΔM > 0 ? '+' : ''}{team.ΔM}
                                </td>
                                <td className={`py-2 px-3 text-center ${team.ΔL > 0 ? 'text-red-400' : team.ΔL < 0 ? 'text-green-400' : 'text-gray-400'}`}>
                                  {team.ΔL > 0 ? '+' : ''}{team.ΔL}
                                </td>
                                <td className="py-2 px-3 text-center text-gray-400">{team['Back-to-backs']}</td>
                                <td className="py-2 px-3 text-center text-gray-400">{team['Long gaps (>=10d)']}</td>
                                <td className="py-2 px-3 text-center text-gray-400">{team['Avg gap (d)']}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              )}


            </div>
          </div>
        </div>
      )}
    </div>
  )
}
