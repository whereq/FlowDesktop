import { useContext } from 'react'
import { WatchlistContext, type WatchlistContextValue } from './WatchlistContext'

export type { WatchlistContextValue }

/** Access the shared watchlist context. Must be used inside <WatchlistProvider>. */
export function useWatchlistContext(): WatchlistContextValue {
  const ctx = useContext(WatchlistContext)
  if (!ctx) throw new Error('useWatchlistContext must be used inside <WatchlistProvider>')
  return ctx
}
