import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import PlayersPage from './pages/PlayersPage'
import PlayerDetailPage from './pages/PlayerDetailPage'
import LeaderboardPage from './pages/LeaderboardPage'
import ImpactPage from './pages/ImpactPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<LeaderboardPage />} />
        <Route path="/players" element={<PlayersPage />} />
        <Route path="/players/:id" element={<PlayerDetailPage />} />
        <Route path="/leaderboard" element={<LeaderboardPage />} />
        <Route path="/impact" element={<ImpactPage />} />
      </Routes>
    </Layout>
  )
}

export default App
