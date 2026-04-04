import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
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
  const [availableSeasons, setAvailableSeasons] = useState<string[]>([])
  const [season, setSeason] = useState('2024-25')
  const [seasonsLoaded, setSeasonsLoaded] = useState(false)

  useEffect(() => {
    api.seasons.list()
      .then(seasons => {
        setAvailableSeasons(seasons)
        if (seasons.length > 0) {
          setSeason(seasons[0])
        }
        setSeasonsLoaded(true)
      })
      .catch(() => setSeasonsLoaded(true))
  }, [])

  return (
    <SeasonContext.Provider value={{ season, setSeason, availableSeasons, seasonsLoaded }}>
      {children}
    </SeasonContext.Provider>
  )
}

export function useSeason() {
  return useContext(SeasonContext)
}
