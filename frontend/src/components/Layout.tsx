import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useState, useEffect } from 'react'
import { useSeason } from '@/context/SeasonContext'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const { season, setSeason, availableSeasons } = useSeason()
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  return (
    <div className="min-h-screen">
      <header className="bg-white dark:bg-gray-900 shadow-sm dark:shadow-gray-800">
        <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <Link to="/" className="text-xl font-bold text-gray-900 dark:text-white">
              CourtVision
            </Link>
            <div className="flex items-center gap-6">
              <Link to="/leaderboard" className="text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
                Leaderboard
              </Link>
              <Link to="/impact" className="text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
                Impact
              </Link>
              <Link to="/play-types" className="text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
                Play Types
              </Link>
              <Link to="/players" className="text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
                Players
              </Link>
              <Link to="/league-leaders" className="text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
                League Leaders
              </Link>
              <Link to="/player-card" className="text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
                Player Card
              </Link>
              {availableSeasons.length > 0 && (
                <select
                  value={season}
                  onChange={e => setSeason(e.target.value)}
                  className="text-sm border border-gray-300 dark:border-gray-600 rounded-md px-2 py-1.5 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  {availableSeasons.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              )}
              <button
                onClick={() => setDark(d => !d)}
                className="px-3 py-1.5 rounded-md text-sm bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
              >
                {dark ? 'Light' : 'Dark'}
              </button>
            </div>
          </div>
        </nav>
      </header>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}
