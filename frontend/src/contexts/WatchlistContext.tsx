import { createContext, useState, useEffect, useCallback, useRef, startTransition, type ReactNode } from 'react'
import { useAuthContext } from '../auth/useAuthContext'
import { api } from '../api/client'
import { lsSet, lsGet, lsRemove } from '../utils/storage'

const WATCHLIST_KEY = 'FlowDesktop_watchlist'

export interface WatchlistContextValue {
  symbols: string[]
  toggle: (symbol: string) => void
  isWatching: (symbol: string) => boolean
}

const WatchlistContext = createContext<WatchlistContextValue | null>(null)

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------
function loadLocal(): string[] {
  const raw = lsGet(WATCHLIST_KEY)
  if (!raw) return []
  try { return JSON.parse(raw) } catch { return [] }
}

function saveLocal(symbols: string[]) {
  lsSet(WATCHLIST_KEY, JSON.stringify(symbols))
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------
export function WatchlistProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuthContext()
  const [symbols, setSymbols] = useState<string[]>([])
  const ref = useRef<string[]>([])
  const synced = useRef(false)

  // ---------- Initial load ----------
  useEffect(() => {
    if (!isAuthenticated) {
      // Anonymous: load from localStorage
      const local = loadLocal()
      ref.current = local
      startTransition(() => setSymbols(local))
      synced.current = false
      return
    }

    // Authenticated: fetch from API, merge any localStorage symbols
    let cancelled = false
    ;(async () => {
      try {
        const { symbols: remote } = await api.getWatchlist()
        if (cancelled) return

        const local = loadLocal()
        const localOnly = local.filter((s) => !remote.includes(s))

        if (localOnly.length > 0) {
          // Merge: append localStorage-only symbols to server list
          const merged = [...remote, ...localOnly]
          const { symbols: final } = await api.replaceWatchlist(merged)
          if (cancelled) return
          ref.current = final
          setSymbols(final)
          // Clear localStorage after successful merge
          lsRemove(WATCHLIST_KEY)
        } else {
          ref.current = remote
          setSymbols(remote)
          // Clear localStorage since server is authoritative
          if (local.length > 0) lsRemove(WATCHLIST_KEY)
        }
        synced.current = true
      } catch {
        // API error — fall back to localStorage
        const local = loadLocal()
        ref.current = local
        setSymbols(local)
      }
    })()

    return () => { cancelled = true }
  }, [isAuthenticated])

  // ---------- Toggle ----------
  const toggle = useCallback((symbol: string) => {
    const sym = symbol.toUpperCase().trim()
    const removing = ref.current.includes(sym)
    const next = removing
      ? ref.current.filter((s) => s !== sym)
      : [...ref.current, sym]

    // Optimistic update
    ref.current = next
    setSymbols(next)

    if (isAuthenticated) {
      // Fire-and-forget API call; on failure, revert
      const prev = removing ? [...next, sym] : next.filter((s) => s !== sym)
      const apiCall = removing
        ? api.removeFromWatchlist(sym)
        : api.addToWatchlist(sym)

      apiCall
        .then(({ symbols: latest }) => {
          ref.current = latest
          setSymbols(latest)
        })
        .catch(() => {
          // Revert on error
          ref.current = prev
          setSymbols(prev)
        })
    } else {
      saveLocal(next)
    }
  }, [isAuthenticated])

  // ---------- isWatching ----------
  const isWatching = useCallback((symbol: string) => ref.current.includes(symbol), [])

  return (
    <WatchlistContext.Provider value={{ symbols, toggle, isWatching }}>
      {children}
    </WatchlistContext.Provider>
  )
}

// Hook (useWatchlistContext) is in ./useWatchlistContext.ts to satisfy react-refresh/only-export-components
export { WatchlistContext }
