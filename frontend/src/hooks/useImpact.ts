import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function useImpactLeaderboard(
  sortBy: 'net' | 'offense' | 'defense' = 'net',
  season?: string,
  limit = 50
) {
  return useQuery({
    queryKey: ['impact-leaderboard', sortBy, season, limit],
    queryFn: () => api.impact.leaderboard(season, sortBy, limit),
  })
}

export function useImpactPlayers(season?: string, limit = 100, offset = 0) {
  return useQuery({
    queryKey: ['impact-players', season, limit, offset],
    queryFn: () => api.impact.list(season, limit, offset),
  })
}

export function usePlayerImpact(playerId: number, season?: string) {
  return useQuery({
    queryKey: ['player-impact', playerId, season],
    queryFn: () => api.impact.get(playerId, season),
    enabled: !!playerId,
  })
}
