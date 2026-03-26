import type { ImpactLeaderboardEntry, Player, PlayerDetail, PlayerImpact, PlayerPerGameStats } from '@/types'
import type { PlayTypeKey, PlayTypeLeaderboardResponse, PlayTypeSortBy, PlayerPlayTypeStats } from '@/types/playType'

const API_BASE = '/api'

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

export const api = {
  players: {
    list: (params?: { season?: string; position?: string; team?: string }) => {
      const searchParams = new URLSearchParams()
      if (params?.season) searchParams.set('season', params.season)
      if (params?.position) searchParams.set('position', params.position)
      if (params?.team) searchParams.set('team', params.team)
      const query = searchParams.toString()
      return fetchJson<Player[]>(`/players${query ? `?${query}` : ''}`)
    },
    get: (id: number, season?: string) => {
      const query = season ? `?season=${season}` : ''
      return fetchJson<PlayerDetail>(`/players/${id}${query}`)
    },
  },
  leaderboards: {
    offensive: (season?: string, limit = 50) =>
      fetchJson<Player[]>(`/leaderboards/offensive?limit=${limit}${season ? `&season=${season}` : ''}`),
    defensive: (season?: string, limit = 50) =>
      fetchJson<Player[]>(`/leaderboards/defensive?limit=${limit}${season ? `&season=${season}` : ''}`),
    overall: (season?: string, limit = 50) =>
      fetchJson<Player[]>(`/leaderboards/overall?limit=${limit}${season ? `&season=${season}` : ''}`),
    perGame: (sortBy: string, season?: string, limit = 10) =>
      fetchJson<PlayerPerGameStats[]>(`/leaderboards/per-game?sort_by=${sortBy}&limit=${limit}${season ? `&season=${season}` : ''}`),
    seasons: () => fetchJson<{ season: string }[]>('/leaderboards/seasons'),
  },
  impact: {
    leaderboard: (season?: string, sortBy: 'net' | 'offense' | 'defense' = 'net', limit = 50) =>
      fetchJson<ImpactLeaderboardEntry[]>(
        `/impact/leaderboard?limit=${limit}&sort_by=${sortBy}${season ? `&season=${season}` : ''}`
      ),
    list: (season?: string, limit = 100, offset = 0) =>
      fetchJson<PlayerImpact[]>(
        `/impact/players?limit=${limit}&offset=${offset}${season ? `&season=${season}` : ''}`
      ),
    get: (playerId: number, season?: string) => {
      const query = season ? `?season=${season}` : ''
      return fetchJson<PlayerImpact>(`/impact/players/${playerId}${query}`)
    },
  },
  playTypes: {
    leaderboard: (
      playType: PlayTypeKey = 'isolation',
      sortBy: PlayTypeSortBy = 'ppp',
      season?: string,
      limit = 50,
      minPoss = 50
    ) =>
      fetchJson<PlayTypeLeaderboardResponse>(
        `/play-types/leaderboard?play_type=${playType}&sort_by=${sortBy}&limit=${limit}&min_poss=${minPoss}${season ? `&season=${season}` : ''}`
      ),
    list: (season?: string, limit = 50, offset = 0) =>
      fetchJson<PlayerPlayTypeStats[]>(
        `/play-types/players?limit=${limit}&offset=${offset}${season ? `&season=${season}` : ''}`
      ),
    get: (playerId: number, season?: string) => {
      const query = season ? `?season=${season}` : ''
      return fetchJson<PlayerPlayTypeStats>(`/play-types/players/${playerId}${query}`)
    },
  },
}
