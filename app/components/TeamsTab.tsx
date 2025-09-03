'use client'

import { useState, useEffect } from 'react'
import { Plus, Trophy, X, Users } from 'lucide-react'
import { supabase, DEFAULT_LEAGUE_ID } from '../../lib/supabase'

interface Team {
  id: number
  league_id: string
  division_id: number
  name: string
  created_at: string
}

interface Division {
  id: number
  league_id: string
  name: string
  created_at: string
}

export default function TeamsTab() {
  const [teams, setTeams] = useState<Team[]>([])
  const [divisions, setDivisions] = useState<Division[]>([])
  const [newDivisionName, setNewDivisionName] = useState('')
  const [newTeamName, setNewTeamName] = useState('')
  const [selectedDivision, setSelectedDivision] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editingTeamId, setEditingTeamId] = useState<number | null>(null)
  const [editingTeamName, setEditingTeamName] = useState('')

  // Load teams from Supabase on component mount
  useEffect(() => {
    loadTeamsFromSupabase()
  }, [])

  const loadTeamsFromSupabase = async () => {
    if (!supabase) {
      console.log('❌ Supabase not available')
      setError('Database connection not available')
      return
    }

    try {
      console.log('🔄 Loading divisions and teams from Supabase...')
      
      // Load divisions
      const { data: divisionsData, error: divisionsError } = await supabase
        .from('divisions')
        .select('*')
        .eq('league_id', DEFAULT_LEAGUE_ID)
        .order('name', { ascending: true })

      if (divisionsError) {
        throw new Error(`Failed to load divisions: ${divisionsError.message}`)
      }

      // Load teams
      const { data: teamsData, error: teamsError } = await supabase
        .from('teams')
        .select('*')
        .eq('league_id', DEFAULT_LEAGUE_ID)
        .order('name', { ascending: true })

      if (teamsError) {
        throw new Error(`Failed to load teams: ${teamsError.message}`)
      }

      console.log('✅ Loaded', divisionsData?.length || 0, 'divisions and', teamsData?.length || 0, 'teams from Supabase')
      setDivisions(divisionsData || [])
      setTeams(teamsData || [])
      setError(null)
    } catch (error) {
      console.error('❌ Error loading teams:', error)
      setError(`Failed to load teams: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const addTeamToSupabase = async (divisionName: string, teamName: string) => {
    if (!supabase) {
      console.log('❌ Supabase not available')
      setError('Database connection not available')
      return
    }

    try {
      console.log('📝 Adding team to Supabase:', divisionName, teamName)
      
      // First, find or create the division
      let divisionId: number
      const existingDivision = divisions.find(d => d.name === divisionName)
      
      if (existingDivision) {
        divisionId = existingDivision.id
      } else {
        // Create new division
        const { data: newDivision, error: divisionError } = await supabase
          .from('divisions')
          .insert({
            league_id: DEFAULT_LEAGUE_ID,
            name: divisionName
          })
          .select()
          .single()

        if (divisionError) {
          throw new Error(`Failed to create division: ${divisionError.message}`)
        }
        divisionId = newDivision.id
      }

      // Add the team
      const { data, error } = await supabase
        .from('teams')
        .insert({
          league_id: DEFAULT_LEAGUE_ID,
          division_id: divisionId,
          name: teamName
        })
        .select()
        .single()

      if (error) {
        throw new Error(`Failed to add team: ${error.message}`)
      }

      console.log('✅ Team added successfully:', data)
      await loadTeamsFromSupabase() // Reload to get updated data
      setError(null)
    } catch (error) {
      console.error('❌ Error adding team:', error)
      setError(`Failed to add team: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const removeTeamFromSupabase = async (teamId: number) => {
    if (!supabase) {
      console.log('❌ Supabase not available')
      setError('Database connection not available')
      return
    }

    try {
      console.log('🗑️ Removing team from Supabase:', teamId)
      const { error } = await supabase
        .from('teams')
        .delete()
        .eq('id', teamId)

      if (error) {
        throw new Error(`Failed to remove team: ${error.message}`)
      }

      console.log('✅ Team removed successfully')
      await loadTeamsFromSupabase() // Reload to get updated data
      setError(null)
    } catch (error) {
      console.error('❌ Error removing team:', error)
      setError(`Failed to remove team: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const addDivision = () => {
    if (newDivisionName.trim()) {
      // Add a placeholder team to create the division
      addTeamToSupabase(newDivisionName.trim(), 'Team 1')
      setNewDivisionName('')
    }
  }

  const addTeam = (divisionName: string) => {
    // Get existing teams in this division
    const existingTeams = teamsByDivision[divisionName] || []
    
    // Extract numbers from existing team names and find the highest
    const teamNumbers = existingTeams.map(team => {
      const match = team.name.match(/Team (\d+)/)
      return match ? parseInt(match[1]) : 0
    })
    
    // Find the next available number
    const nextNumber = teamNumbers.length > 0 ? Math.max(...teamNumbers) + 1 : 1
    const teamName = `Team ${nextNumber}`
    addTeamToSupabase(divisionName, teamName)
  }

  const removeTeam = (teamId: number) => {
    removeTeamFromSupabase(teamId)
  }

  const removeDivision = async (divisionName: string) => {
    if (!supabase) {
      console.log('❌ Supabase not available')
      setError('Database connection not available')
      return
    }

    try {
      console.log('🗑️ Removing division from Supabase:', divisionName)
      
      // Find the division
      const division = divisions.find(d => d.name === divisionName)
      if (!division) {
        throw new Error('Division not found')
      }

      // Delete all teams in this division
      const { error: teamsError } = await supabase
        .from('teams')
        .delete()
        .eq('division_id', division.id)

      if (teamsError) {
        throw new Error(`Failed to remove teams: ${teamsError.message}`)
      }

      // Delete the division
      const { error: divisionError } = await supabase
        .from('divisions')
        .delete()
        .eq('id', division.id)

      if (divisionError) {
        throw new Error(`Failed to remove division: ${divisionError.message}`)
      }

      console.log('✅ Division removed successfully')
      await loadTeamsFromSupabase() // Reload to get updated data
      setError(null)
    } catch (error) {
      console.error('❌ Error removing division:', error)
      setError(`Failed to remove division: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const updateTeamName = async (teamId: number, newName: string) => {
    if (!supabase) {
      console.log('❌ Supabase not available')
      setError('Database connection not available')
      return
    }

    try {
      console.log('📝 Updating team name in Supabase:', teamId, newName)
      const { error } = await supabase
        .from('teams')
        .update({ name: newName })
        .eq('id', teamId)

      if (error) {
        throw new Error(`Failed to update team name: ${error.message}`)
      }

      console.log('✅ Team name updated successfully')
      await loadTeamsFromSupabase() // Reload to get updated data
      setError(null)
    } catch (error) {
      console.error('❌ Error updating team name:', error)
      setError(`Failed to update team name: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const startEditing = (team: Team) => {
    setEditingTeamId(team.id)
    setEditingTeamName(team.name)
  }

  const saveTeamName = () => {
    if (editingTeamId && editingTeamName.trim()) {
      updateTeamName(editingTeamId, editingTeamName.trim())
      setEditingTeamId(null)
      setEditingTeamName('')
    }
  }

  const cancelEditing = () => {
    setEditingTeamId(null)
    setEditingTeamName('')
  }

  // Group teams by division and sort them numerically
  const teamsByDivision = divisions.reduce((acc, division) => {
    const divisionTeams = teams.filter(team => team.division_id === division.id)
    
    // Sort teams numerically by extracting the number from "Team X"
    const sortedTeams = divisionTeams.sort((a, b) => {
      const aMatch = a.name.match(/Team (\d+)/)
      const bMatch = b.name.match(/Team (\d+)/)
      
      if (aMatch && bMatch) {
        return parseInt(aMatch[1]) - parseInt(bMatch[1])
      }
      
      // Fallback to alphabetical sorting for non-standard team names
      return a.name.localeCompare(b.name)
    })
    
    acc[division.name] = sortedTeams
    console.log(`📊 Division "${division.name}": ${sortedTeams.length} teams`, sortedTeams.map(t => t.name))
    return acc
  }, {} as Record<string, Team[]>)

  console.log('🔍 Total teams in state:', teams.length)
  console.log('🔍 Teams by division:', teamsByDivision)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Trophy className="w-6 h-6" />
          Teams & Divisions
        </h2>
        <div className="text-sm text-gray-400 mt-2">
          Total teams: {teams.length} | Total divisions: {divisions.length}
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="flex items-center gap-2 text-red-400 bg-red-900/20 border border-red-800 rounded-lg p-4">
          <X className="w-5 h-5" />
          <span>{error}</span>
        </div>
      )}

      {/* Add Division */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Plus className="w-5 h-5" />
          Add Division
        </h3>
        <div className="flex gap-4">
          <input
            type="text"
            value={newDivisionName}
            onChange={(e) => setNewDivisionName(e.target.value)}
            placeholder="Enter division name..."
            className="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500"
            onKeyPress={(e) => e.key === 'Enter' && addDivision()}
          />
          <button
            onClick={addDivision}
            disabled={!newDivisionName.trim()}
            className="bg-red-600 hover:bg-red-700 disabled:bg-gray-600 px-6 py-2 rounded-lg font-medium transition-colors"
          >
            Add Division
          </button>
        </div>
      </div>

      {/* Teams List */}
      {teams.length > 0 ? (
        <div className="space-y-4">
          {divisions.map((division) => (
            <div key={division.id} className="bg-gray-800 rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <Trophy className="w-5 h-5" />
                    {division.name}
                  </h3>
                  <button
                    onClick={() => removeDivision(division.name)}
                    className="text-red-400 hover:text-red-300 transition-colors"
                    title="Remove entire division"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-gray-400">
                    {teamsByDivision[division.name]?.length || 0} team{(teamsByDivision[division.name]?.length || 0) !== 1 ? 's' : ''}
                  </span>
                  <button
                    onClick={() => addTeam(division.name)}
                    className="bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded text-sm font-medium flex items-center gap-1 transition-colors"
                  >
                    <Plus className="w-3 h-3" />
                    Add Team
                  </button>
                </div>
              </div>

              {/* Teams List */}
              <div className="space-y-2">
                {(teamsByDivision[division.name] || []).map((team) => (
                  <div key={team.id} className="flex items-center justify-between bg-gray-700 rounded-lg px-4 py-3">
                    <div className="flex items-center gap-2 flex-1">
                      <Users className="w-4 h-4 text-gray-400" />
                      {editingTeamId === team.id ? (
                        <div className="flex items-center gap-2 flex-1">
                          <input
                            type="text"
                            value={editingTeamName}
                            onChange={(e) => setEditingTeamName(e.target.value)}
                            className="flex-1 bg-gray-600 border border-gray-500 rounded px-2 py-1 text-white focus:outline-none focus:ring-2 focus:ring-red-500"
                            onKeyPress={(e) => {
                              if (e.key === 'Enter') saveTeamName()
                              if (e.key === 'Escape') cancelEditing()
                            }}
                            autoFocus
                          />
                          <button
                            onClick={saveTeamName}
                            className="text-green-400 hover:text-green-300 transition-colors"
                            title="Save"
                          >
                            ✓
                          </button>
                          <button
                            onClick={cancelEditing}
                            className="text-gray-400 hover:text-gray-300 transition-colors"
                            title="Cancel"
                          >
                            ✕
                          </button>
                        </div>
                      ) : (
                        <span 
                          className="cursor-pointer hover:text-gray-300 transition-colors"
                          onClick={() => startEditing(team)}
                          title="Click to edit team name"
                        >
                          {team.name}
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => removeTeam(team.id)}
                      className="text-red-400 hover:text-red-300 transition-colors ml-2"
                      title="Remove team"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg p-6 text-center">
          <Trophy className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-400">No teams added yet.</p>
          <p className="text-gray-500 text-sm mt-2">Add teams above to start building your league structure.</p>
        </div>
      )}
    </div>
  )
}
