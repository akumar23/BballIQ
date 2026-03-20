import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen">
      <header className="bg-white shadow-sm">
        <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <Link to="/" className="text-xl font-bold text-gray-900">
              StatFloor
            </Link>
            <div className="flex gap-6">
              <Link to="/leaderboard" className="text-gray-600 hover:text-gray-900">
                Leaderboard
              </Link>
              <Link to="/impact" className="text-gray-600 hover:text-gray-900">
                Impact
              </Link>
              <Link to="/play-types" className="text-gray-600 hover:text-gray-900">
                Play Types
              </Link>
              <Link to="/players" className="text-gray-600 hover:text-gray-900">
                Players
              </Link>
              <Link to="/league-leaders" className="text-gray-600 hover:text-gray-900">
                League Leaders
              </Link>
              <Link to="/player-card" className="text-gray-600 hover:text-gray-900">
                Player Card
              </Link>
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
