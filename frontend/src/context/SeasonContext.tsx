import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

interface SeasonContextValue {
  season: string
  setSeason: (s: string) => void
  availableSeasons: string[]
  seasonsLoaded: boolean
}

const SeasonContext = createContext<SeasonContextValue>({
  season: '2024-25',
  setSeason: () => {},
  availableSeasons: [],
  seasonsLoaded: false,
})

export function SeasonProvider({ children }: { children: ReactNode }) {
  // Delegate the fetch to React Query so error/retry/cache behavior is consistent
  // with the rest of the app. The provider still exposes the same shape.
  const { data, isSuccess, isError } = useQuery({
    queryKey: ['seasons'],
    queryFn: () => api.seasons.list(),
  })

  const availableSeasons = data ?? []
  const [season, setSeason] = useState('2024-25')
  const [hasDefaulted, setHasDefaulted] = useState(false)
  const seasonsLoaded = isSuccess || isError

  // Default the active season to the first returned entry on initial load,
  // matching the previous provider's behavior. Only runs once.
  useEffect(() => {
    if (!hasDefaulted && isSuccess && availableSeasons.length > 0) {
      setSeason(availableSeasons[0])
      setHasDefaulted(true)
    }
  }, [hasDefaulted, isSuccess, availableSeasons])

  return (
    <SeasonContext.Provider value={{ season, setSeason, availableSeasons, seasonsLoaded }}>
      {children}
    </SeasonContext.Provider>
  )
}

export function useSeason() {
  return useContext(SeasonContext)
}
