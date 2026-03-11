import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { PlayTypeKey, PlayTypeSortBy } from '@/types/playType'

export function usePlayTypeLeaderboard(
  playType: PlayTypeKey = 'isolation',
  sortBy: PlayTypeSortBy = 'ppp',
  season?: string,
  limit = 50,
  minPoss = 50
) {
  return useQuery({
    queryKey: ['play-type-leaderboard', playType, sortBy, season, limit, minPoss],
    queryFn: () => api.playTypes.leaderboard(playType, sortBy, season, limit, minPoss),
  })
}

export function usePlayTypePlayers(season?: string, limit = 50, offset = 0) {
  return useQuery({
    queryKey: ['play-type-players', season, limit, offset],
    queryFn: () => api.playTypes.list(season, limit, offset),
  })
}

export function usePlayerPlayTypes(playerId: number, season?: string) {
  return useQuery({
    queryKey: ['player-play-types', playerId, season],
    queryFn: () => api.playTypes.get(playerId, season),
    enabled: !!playerId,
  })
}
