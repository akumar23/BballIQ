import { lazy, Suspense, type ReactNode } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ErrorBoundary from './components/ErrorBoundary'
import { SeasonProvider } from './context/SeasonContext'

// Heavy pages (charts via recharts/d3, data-dense tables) are code-split so
// the initial bundle only loads what's needed for the first route.
const PlayersPage = lazy(() => import('./pages/PlayersPage'))
const PlayerDetailPage = lazy(() => import('./pages/PlayerDetailPage'))
const LeaderboardPage = lazy(() => import('./pages/LeaderboardPage'))
const LeagueLeadersPage = lazy(() => import('./pages/LeagueLeadersPage'))
const ImpactPage = lazy(() => import('./pages/ImpactPage'))
const PlayTypesPage = lazy(() => import('./pages/PlayTypesPage'))
const PlayerCardPage = lazy(() => import('./pages/PlayerCardPage'))

function RouteFallback() {
  return (
    <div className="flex items-center justify-center h-64" role="status" aria-live="polite">
      <p className="text-gray-400 font-mono text-sm animate-pulse">Loading…</p>
    </div>
  )
}

/**
 * Wraps a lazy-loaded route element with an isolating ErrorBoundary plus a
 * Suspense fallback. The boundary sits *outside* Suspense so that a render
 * error in the resolved module is caught by the boundary, while the fallback
 * only shows during the async import.
 */
function RouteElement({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary compact>
      <Suspense fallback={<RouteFallback />}>{children}</Suspense>
    </ErrorBoundary>
  )
}

function App() {
  return (
    <ErrorBoundary>
      <SeasonProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<RouteElement><LeaderboardPage /></RouteElement>} />
            <Route path="/league-leaders" element={<RouteElement><LeagueLeadersPage /></RouteElement>} />
            <Route path="/players" element={<RouteElement><PlayersPage /></RouteElement>} />
            <Route path="/players/:id" element={<RouteElement><PlayerDetailPage /></RouteElement>} />
            <Route path="/leaderboard" element={<RouteElement><LeaderboardPage /></RouteElement>} />
            <Route path="/impact" element={<RouteElement><ImpactPage /></RouteElement>} />
            <Route path="/play-types" element={<RouteElement><PlayTypesPage /></RouteElement>} />
            <Route path="/player-card" element={<RouteElement><PlayerCardPage /></RouteElement>} />
          </Routes>
        </Layout>
      </SeasonProvider>
    </ErrorBoundary>
  )
}

export default App
