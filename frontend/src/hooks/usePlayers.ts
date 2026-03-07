import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function usePlayers(params?: { season?: string; position?: string; team?: string }) {
  return useQuery({
    queryKey: ['players', params],
    queryFn: () => api.players.list(params),
  })
}

export function usePlayer(id: number, season?: string) {
  return useQuery({
    queryKey: ['player', id, season],
    queryFn: () => api.players.get(id, season),
    enabled: !!id,
  })
}

export function useLeaderboard(type: 'offensive' | 'defensive' | 'overall', season?: string) {
  return useQuery({
    queryKey: ['leaderboard', type, season],
    queryFn: () => api.leaderboards[type](season),
  })
}
