'use client'

import { useState, useEffect } from 'react'
import { Upload, Trophy, Calendar, Settings } from 'lucide-react'
import ImportTab from './components/ImportTab'
import TeamsTab from './components/TeamsTab'
import ScheduleTab from './components/ScheduleTab'
import ParametersTab from './components/ParametersTab'
import { SchedulerParamsData, DEFAULT_PARAMS } from '@/lib/types'

type Tab = 'import' | 'teams' | 'schedule' | 'parameters'

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('import')
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [slots, setSlots] = useState<any[]>([])
  const [teams, setTeams] = useState<any[]>([])
  const [divisions, setDivisions] = useState<any[]>([])
  const [params, setParams] = useState<SchedulerParamsData>(() => {
    // Load from localStorage on initial load
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('schedulerParams')
      if (saved) {
        return JSON.parse(saved)
      }
    }
    return DEFAULT_PARAMS
  })
  const [emlThresholds, setEmlThresholds] = useState(() => {
    // Load from localStorage on initial load
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('emlThresholds')
      if (saved) {
        return JSON.parse(saved)
      }
    }
    // Default to the same values as the scheduler parameters
    return {
      earlyStart: '22:01', // Early games start before 10:01 PM
      midStart: '22:31'    // Mid games start before 10:31 PM
    }
  })

  // Sync emlThresholds with params.eml when params change
  useEffect(() => {
    console.log('🔍 Main page params.eml:', params.eml)
    console.log('🔍 Main page emlThresholds:', emlThresholds)
    
    if (params.eml && (params.eml.earlyStart !== emlThresholds.earlyStart || params.eml.midStart !== emlThresholds.midStart)) {
      console.log('🔄 Syncing emlThresholds with params.eml')
      setEmlThresholds({
        earlyStart: params.eml.earlyStart,
        midStart: params.eml.midStart
      })
    }
  }, [params.eml])

  const [amountOfGames, setAmountOfGames] = useState(() => {
    // Load from localStorage on initial load
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('amountOfGames')
      if (saved) {
        return parseInt(saved)
      }
    }
    return 12 // Default to 12 games
  })

  // Wrapper function to save all params to localStorage
  const updateParams = (newParams: SchedulerParamsData) => {
    setParams(newParams)
    if (typeof window !== 'undefined') {
      localStorage.setItem('schedulerParams', JSON.stringify(newParams))
    }
  }

  // Wrapper function to save to localStorage when thresholds change
  const updateEmlThresholds = (newThresholds: { earlyStart: string; midStart: string }) => {
    setEmlThresholds(newThresholds)
    if (typeof window !== 'undefined') {
      localStorage.setItem('emlThresholds', JSON.stringify(newThresholds))
    }
  }

  // Wrapper function to save to localStorage when amount of games change
  const updateAmountOfGames = (newAmount: number) => {
    setAmountOfGames(newAmount)
    if (typeof window !== 'undefined') {
      localStorage.setItem('amountOfGames', newAmount.toString())
    }
  }

  const tabs = [
    { id: 'import', label: 'Import', icon: Upload },
    { id: 'teams', label: 'Teams', icon: Trophy },
    { id: 'parameters', label: 'Parameters', icon: Settings },
    { id: 'schedule', label: 'Schedule', icon: Calendar },
  ]

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <h1 className="text-xl font-bold">
                  League Scheduler
                </h1>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-8">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as Tab)}
                  className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2 transition-colors ${
                    activeTab === tab.id
                      ? 'border-red-500 text-red-500'
                      : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-300'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              )
            })}
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'import' && (
          <ImportTab 
            uploadedFile={uploadedFile}
            setUploadedFile={setUploadedFile}
            slots={slots}
            setSlots={setSlots}
            emlThresholds={emlThresholds}
          />
        )}
        {activeTab === 'teams' && (
          <TeamsTab />
        )}
        {activeTab === 'schedule' && (
          <ScheduleTab 
            slots={slots}
            teams={[]} // We'll load this from Supabase in the component
            divisions={[]} // We'll load this from Supabase in the component
            params={{
              ...params,
              eml: emlThresholds,
              gamesPerTeam: amountOfGames
            }}
          />
        )}
        {activeTab === 'parameters' && (
          <ParametersTab 
            emlThresholds={emlThresholds}
            setEmlThresholds={updateEmlThresholds}
            amountOfGames={amountOfGames}
            setAmountOfGames={updateAmountOfGames}
            params={params}
            setParams={updateParams}
          />
        )}
      </main>
    </div>
  )
}
