'use client'

import { useState, useEffect, useRef } from 'react'
import { Settings, Save, Target, Clock, Calendar } from 'lucide-react'
import { SchedulerParamsData, DEFAULT_PARAMS } from '@/lib/types'
import { saveParamsAction, getLatestParamsAction } from '@/app/actions/parameters'


interface ParametersTabProps {
  emlThresholds: {
    earlyStart: string  // Maps to earlyEnd in scheduler
    midStart: string    // Maps to midEnd in scheduler
  }
  setEmlThresholds: (thresholds: { earlyStart: string; midStart: string }) => void
  amountOfGames: number
  setAmountOfGames: (amount: number) => void
  params: SchedulerParamsData
  setParams: (params: SchedulerParamsData) => void
}

export default function ParametersTab({ emlThresholds, setEmlThresholds, amountOfGames, setAmountOfGames, params, setParams }: ParametersTabProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')
  const [error, setError] = useState('')
  const saveDebounceRef = useRef<NodeJS.Timeout | null>(null)

  // Load saved parameters on mount (prefer local draft, then server)
  useEffect(() => {
    const draft = typeof window !== 'undefined' ? localStorage.getItem('scheduler_params_draft') : null
    if (draft) {
      try {
        const parsed = JSON.parse(draft)
        setParams(parsed)
        setEmlThresholds(parsed.eml)
        setAmountOfGames(parsed.gamesPerTeam)
        // Also kick a background save to ensure server snapshot
        void saveParamsAction(parsed)
        return
      } catch (_) {
        // fall through to server load
      }
    }
    loadSavedParams()
  }, [])

  // Keep parent state in sync when the inputs for EML and games change
  useEffect(() => {
    const newParams = {
      ...params,
      eml: emlThresholds,
      gamesPerTeam: amountOfGames
    }
    if (JSON.stringify(params.eml) !== JSON.stringify(emlThresholds) || 
        params.gamesPerTeam !== amountOfGames) {
      setParams(newParams)
    }
  }, [emlThresholds, amountOfGames])

  // Persist params locally and debounced-save to server whenever params change
  useEffect(() => {
    try {
      if (typeof window !== 'undefined') {
        localStorage.setItem('scheduler_params_draft', JSON.stringify(params))
      }
    } catch (_) {}

    if (saveDebounceRef.current) clearTimeout(saveDebounceRef.current)
    saveDebounceRef.current = setTimeout(async () => {
      try {
        await saveParamsAction(params)
      } catch (e) {
        // Swallow errors; user can still click explicit Save
        console.error('Auto-save failed:', e)
      }
    }, 800)

    return () => {
      if (saveDebounceRef.current) clearTimeout(saveDebounceRef.current)
    }
  }, [params])

  const loadSavedParams = async () => {
    try {
      const result = await getLatestParamsAction()
      if (result.success && result.data) {
        // Use the params from the result, or default params if none exist
        const paramsToUse = result.data.params || DEFAULT_PARAMS
        setParams(paramsToUse)
        // Update parent state
        setEmlThresholds(paramsToUse.eml)
        setAmountOfGames(paramsToUse.gamesPerTeam)
      } else {
        // If loading failed, use default params
        setParams(DEFAULT_PARAMS)
        setEmlThresholds(DEFAULT_PARAMS.eml)
        setAmountOfGames(DEFAULT_PARAMS.gamesPerTeam)
      }
    } catch (error) {
      console.error('Error loading parameters:', error)
      // Use default params on error
      setParams(DEFAULT_PARAMS)
      setEmlThresholds(DEFAULT_PARAMS.eml)
      setAmountOfGames(DEFAULT_PARAMS.gamesPerTeam)
    }
  }

  const handleSave = async () => {
    setIsLoading(true)
    setError('')
    
    try {
      const result = await saveParamsAction(params)
      if (result.success) {
        setSaveMessage('Parameters saved successfully!')
        setTimeout(() => setSaveMessage(''), 3000)
      } else {
        setError('Failed to save parameters')
      }
    } catch (error) {
      setError('Failed to save parameters')
      console.error('Save error:', error)
    } finally {
      setIsLoading(false)
    }
  }



  const updateParam = (key: keyof SchedulerParamsData, value: any) => {
    setParams({ ...params, [key]: value })
  }

  const updateEmlParam = (key: keyof SchedulerParamsData['eml'], value: string) => {
    const newParams = { 
      ...params, 
      eml: { ...params.eml, [key]: value } 
    }
    setParams(newParams)
    // Also update parent state with the new eml values
    setEmlThresholds(newParams.eml)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Settings className="w-6 h-6" />
          Scheduling Parameters
        </h2>
        <div className="flex gap-2">
          <button
            onClick={handleSave}
            disabled={isLoading}
            className="bg-red-600 hover:bg-red-700 disabled:bg-gray-600 px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors"
          >
            <Save className="w-4 h-4" />
            {isLoading ? 'Saving...' : 'Save Settings'}
          </button>

        </div>
      </div>

      {/* Save Message */}
      {saveMessage && (
        <div className="bg-green-900/20 border border-green-800 rounded-lg p-4 text-green-400">
          {saveMessage}
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-400">
          {error}
        </div>
      )}

      {/* Amount of Games */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Target className="w-5 h-5" />
          Amount of Games
        </h3>
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Number of Games per Team
          </label>
          <input
            type="number"
            min="1"
            step="1"
            value={params.gamesPerTeam}
            onChange={(e) => {
              const value = parseInt(e.target.value) || 1
              updateParam('gamesPerTeam', value)
              setAmountOfGames(value)
            }}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-red-500"
          />
          <p className="text-xs text-gray-400 mt-1">
            Total number of games each team will play in the season
          </p>
        </div>
      </div>

      {/* E/M/L Time Thresholds */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Clock className="w-5 h-5" />
          Early / Mid / Late
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Early End Time (Early games end before this time)
            </label>
            <input
              type="time"
              value={params.eml.earlyStart}
              onChange={(e) => updateEmlParam('earlyStart', e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-red-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              Games ending before this time are considered "Early"
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Mid End Time (Mid games end before this time)
            </label>
            <input
              type="time"
              value={params.eml.midStart}
              onChange={(e) => updateEmlParam('midStart', e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-red-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              Games ending before this time are considered "Mid"
            </p>
          </div>
        </div>
      </div>

      {/* Rules */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
          <Calendar className="w-5 h-5" />
          Rules
        </h3>

        {/* Hard Constraints */}
        <div className="mb-8">
          <h4 className="text-lg font-semibold text-red-400 mb-4 flex items-center gap-2">
            <div className="w-3 h-3 bg-red-500 rounded-full"></div>
            Hard Constraints
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
              <div>
                <div className="font-medium">🚫 No Back-to-Back Games</div>
                <div className="text-sm text-gray-400">Teams can't play each other twice in a row</div>
              </div>
              <input
                type="checkbox"
                checked={params.noBackToBack}
                onChange={(e) => updateParam('noBackToBack', e.target.checked)}
                className="w-5 h-5 text-red-600 bg-gray-600 border-gray-500 rounded focus:ring-red-500"
              />
            </div>

            <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
              <div>
                <div className="font-medium">🔀 Sub Division Crossover</div>
                <div className="text-sm text-gray-400">Allows teams from different sub-divisions to play against each other</div>
              </div>
              <input
                type="checkbox"
                checked={params.subDivisionCrossover}
                onChange={(e) => updateParam('subDivisionCrossover', e.target.checked)}
                className="w-5 h-5 text-red-600 bg-gray-600 border-gray-500 rounded focus:ring-red-500"
              />
            </div>

            <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
              <div>
                <div className="font-medium">🚫 No Inter-Division Games</div>
                <div className="text-sm text-gray-400">Prevents teams from different divisions from playing each other</div>
              </div>
              <input
                type="checkbox"
                checked={params.noInterdivision}
                onChange={(e) => updateParam('noInterdivision', e.target.checked)}
                className="w-5 h-5 text-red-600 bg-gray-600 border-gray-500 rounded focus:ring-red-500"
              />
            </div>

            <div className="p-4 bg-gray-700 rounded-lg">
              <div className="font-medium">🎯 Target/Ideal Gap (~7)</div>
              <div className="text-sm text-gray-400 mb-3">Tries to keep cadence around 1 game/week; soft objective</div>
              <input
                type="number"
                min="3"
                max="14"
                value={params.idealGapDays}
                onChange={(e) => updateParam('idealGapDays', parseInt(e.target.value) || 7)}
                className="w-24 bg-gray-600 border border-gray-500 rounded px-2 py-1 text-white focus:outline-none focus:ring-2 focus:ring-red-500"
              />
              <span className="text-sm text-gray-400 ml-2">days</span>
            </div>

            <div className="p-4 bg-gray-700 rounded-lg">
              <div className="font-medium">⏰ Min Rest Days</div>
              <div className="text-sm text-gray-400 mb-3">A team must have at least X days off between games</div>
              <input
                type="number"
                min="0"
                value={params.minRestDays}
                onChange={(e) => updateParam('minRestDays', parseInt(e.target.value) || 0)}
                className="w-24 bg-gray-600 border border-gray-500 rounded px-2 py-1 text-white focus:outline-none focus:ring-2 focus:ring-red-500"
              />
              <span className="text-sm text-gray-400 ml-2">days</span>
            </div>

            <div className="p-4 bg-gray-700 rounded-lg">
              <div className="font-medium">📅 Max Idle Gap</div>
              <div className="text-sm text-gray-400 mb-3">No team should go more than Y days without a game</div>
              <input
                type="number"
                min="1"
                value={params.maxGapDays}
                onChange={(e) => updateParam('maxGapDays', parseInt(e.target.value) || 1)}
                className="w-24 bg-gray-600 border border-gray-500 rounded px-2 py-1 text-white focus:outline-none focus:ring-2 focus:ring-red-500"
              />
              <span className="text-sm text-gray-400 ml-2">days</span>
            </div>
          </div>
        </div>

        {/* Balance Goals */}
        <div className="mb-8">
          <h4 className="text-lg font-semibold text-orange-400 mb-4 flex items-center gap-2">
            <div className="w-3 h-3 bg-orange-500 rounded-full"></div>
            Balance Goals
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
              <div>
                <div className="font-medium">⚖️ Balance Home and Away</div>
                <div className="text-sm text-gray-400">Ensures teams have balanced home/away game distribution</div>
              </div>
              <input
                type="checkbox"
                checked={params.homeAwayBalance}
                onChange={(e) => updateParam('homeAwayBalance', e.target.checked)}
                className="w-5 h-5 text-orange-600 bg-gray-600 border-gray-500 rounded focus:ring-orange-500"
              />
            </div>

            <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
              <div>
                <div className="font-medium">📊 Variance Minimization</div>
                <div className="text-sm text-gray-400">Reduces variance in game gaps across all teams</div>
              </div>
              <input
                type="checkbox"
                checked={params.varianceMinimization}
                onChange={(e) => updateParam('varianceMinimization', e.target.checked)}
                className="w-5 h-5 text-orange-600 bg-gray-600 border-gray-500 rounded focus:ring-orange-500"
              />
            </div>

            <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
              <div>
                <div className="font-medium">📅 Weekday Balance</div>
                <div className="text-sm text-gray-400">Balances games across different days of the week</div>
              </div>
              <input
                type="checkbox"
                checked={params.weekdayBalance}
                onChange={(e) => updateParam('weekdayBalance', e.target.checked)}
                className="w-5 h-5 text-orange-600 bg-gray-600 border-gray-500 rounded focus:ring-orange-500"
              />
            </div>
          </div>
        </div>

        {/* Enhancements */}
        <div>
          <h4 className="text-lg font-semibold text-green-400 mb-4 flex items-center gap-2">
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            Enhancements
          </h4>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
              <div>
                <div className="font-medium">🎄 Holiday Awareness</div>
                <div className="text-sm text-gray-400">Avoids scheduling games on major holidays</div>
              </div>
              <input
                type="checkbox"
                checked={params.holidayAwareness}
                onChange={(e) => updateParam('holidayAwareness', e.target.checked)}
                className="w-5 h-5 text-green-600 bg-gray-600 border-gray-500 rounded focus:ring-green-500"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
