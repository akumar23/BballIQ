import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import PlayersPage from './pages/PlayersPage'
import PlayerDetailPage from './pages/PlayerDetailPage'
import LeaderboardPage from './pages/LeaderboardPage'
import LeagueLeadersPage from './pages/LeagueLeadersPage'
import ImpactPage from './pages/ImpactPage'
import PlayTypesPage from './pages/PlayTypesPage'
import PlayerCardPage from './pages/PlayerCardPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<LeaderboardPage />} />
        <Route path="/league-leaders" element={<LeagueLeadersPage />} />
        <Route path="/players" element={<PlayersPage />} />
        <Route path="/players/:id" element={<PlayerDetailPage />} />
        <Route path="/leaderboard" element={<LeaderboardPage />} />
        <Route path="/impact" element={<ImpactPage />} />
        <Route path="/play-types" element={<PlayTypesPage />} />
        <Route path="/player-card" element={<PlayerCardPage />} />
      </Routes>
    </Layout>
  )
}

export default App
