import { NavLink, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { useSeason } from '@/context/SeasonContext'
import { cn } from '@/lib/utils'

interface LayoutProps {
  children: ReactNode
}

const NAV_ITEMS: { to: string; label: string }[] = [
  { to: '/leaderboard', label: 'Leaderboard' },
  { to: '/impact', label: 'Impact' },
  { to: '/play-types', label: 'Play Types' },
  { to: '/players', label: 'Players' },
  { to: '/league-leaders', label: 'League Leaders' },
  { to: '/player-card', label: 'Player Card' },
]

export default function Layout({ children }: LayoutProps) {
  const { season, setSeason, availableSeasons } = useSeason()
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  // Apply saved theme on mount with no transition.
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Auto-close the mobile drawer on route change so the drawer never
  // persists across navigations.
  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  const toggleDark = () => {
    const next = !dark
    setDark(next)
    localStorage.setItem('theme', next ? 'dark' : 'light')
    document.documentElement.classList.add('theme-transitioning')
    requestAnimationFrame(() => {
      document.documentElement.classList.toggle('dark', next)
      window.setTimeout(() => document.documentElement.classList.remove('theme-transitioning'), 100)
    })
  }

  const desktopLinkClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      'relative inline-flex items-center h-16 px-1 text-sm font-medium transition-colors',
      isActive
        ? 'text-primary-600 dark:text-primary-400 border-b-2 border-primary-600 dark:border-primary-400'
        : 'text-gray-600 dark:text-gray-200 hover:text-gray-900 dark:hover:text-white border-b-2 border-transparent',
    )

  const mobileLinkClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      'relative flex items-center pl-4 pr-3 py-3 text-base font-medium transition-colors',
      isActive
        ? 'text-primary-600 dark:text-primary-400 bg-primary-50 dark:bg-primary-500/10 border-l-4 border-primary-600 dark:border-primary-400'
        : 'text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 border-l-4 border-transparent',
    )

  return (
    <div className="min-h-screen">
      {/* Skip link — visible only when focused; first focusable element. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:rounded focus:bg-primary-600 focus:text-white focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
      >
        Skip to content
      </a>

      <header className="bg-white dark:bg-gray-900 shadow-sm dark:shadow-gray-800 sticky top-0 z-30">
        <nav aria-label="Primary" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <NavLink to="/" className="text-xl font-bold text-gray-900 dark:text-white">
              CourtVision
            </NavLink>

            {/* Desktop nav */}
            <div className="hidden md:flex md:items-center md:gap-6">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={desktopLinkClass}
>
                  {item.label}
                </NavLink>
              ))}
              {availableSeasons.length > 0 && (
                <>
                  <label htmlFor="layout-season-select" className="sr-only">
                    Season
                  </label>
                  <select
                    id="layout-season-select"
                    value={season}
                    onChange={(e) => setSeason(e.target.value)}
                    className="text-sm border border-gray-300 dark:border-gray-600 rounded-md px-2 py-1.5 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  >
                    {availableSeasons.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </>
              )}
              <button
                type="button"
                onClick={toggleDark}
                aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
                className="px-3 py-1.5 rounded-md text-sm bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
              >
                {dark ? 'Light' : 'Dark'}
              </button>
            </div>

            {/* Mobile hamburger */}
            <button
              type="button"
              className="md:hidden inline-flex items-center justify-center w-10 h-10 rounded-md text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800"
              aria-label="Toggle navigation menu"
              aria-expanded={mobileOpen}
              aria-controls="mobile-nav-drawer"
              onClick={() => setMobileOpen((o) => !o)}
            >
              {/* Pure SVG hamburger / close icon — no extra deps. */}
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
                className="w-6 h-6"
                aria-hidden="true"
              >
                {mobileOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>

          {/* Mobile drawer */}
          {mobileOpen && (
            <div
              id="mobile-nav-drawer"
              className="md:hidden border-t border-gray-200 dark:border-gray-700 pb-3"
            >
              <div className="flex flex-col py-1">
                {NAV_ITEMS.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={mobileLinkClass}
                  >
                    {item.label}
                  </NavLink>
                ))}
              </div>
              {/* Drawer footer: season + theme toggle stay reachable on mobile. */}
              <div className="flex items-center gap-2 px-4 pt-3 border-t border-gray-200 dark:border-gray-700">
                {availableSeasons.length > 0 && (
                  <>
                    <label htmlFor="layout-season-select-mobile" className="sr-only">
                      Season
                    </label>
                    <select
                      id="layout-season-select-mobile"
                      value={season}
                      onChange={(e) => setSeason(e.target.value)}
                      className="flex-1 text-sm border border-gray-300 dark:border-gray-600 rounded-md px-2 py-2 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-500"
                    >
                      {availableSeasons.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </>
                )}
                <button
                  type="button"
                  onClick={toggleDark}
                  aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
                  className="px-3 py-2 rounded-md text-sm bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                >
                  {dark ? 'Light' : 'Dark'}
                </button>
              </div>
            </div>
          )}
        </nav>
      </header>

      <main id="main-content" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}
