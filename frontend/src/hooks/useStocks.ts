import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type AlertType } from '../api/client'
import { useWatchlistContext } from '../contexts/useWatchlistContext'

/**
 * Shared watchlist — reads from React context so all components stay in sync.
 * App must be wrapped in <WatchlistProvider> (see App.tsx).
 */
export function useWatchlist() {
  return useWatchlistContext()
}

export function useStocks(params?: { skip?: number; limit?: number; sector?: string; exchanges?: string[]; symbols?: string[] }) {
  return useQuery({
    queryKey: ['stocks', params],
    queryFn: () => api.getStocks(params),
  })
}

export function useStock(symbol: string) {
  return useQuery({
    queryKey: ['stock', symbol],
    queryFn: () => api.getStock(symbol),
    enabled: !!symbol,
  })
}

export function useSearchStocks(query: string) {
  return useQuery({
    queryKey: ['search', query],
    queryFn: () => api.searchStocks(query),
    enabled: query.length >= 1,
  })
}

export function useSectors() {
  return useQuery({
    queryKey: ['sectors'],
    queryFn: api.getSectors,
  })
}

export function useExchanges() {
  return useQuery({
    queryKey: ['exchanges'],
    queryFn: api.getExchanges,
  })
}

export function useMarketOverview() {
  return useQuery({
    queryKey: ['market-overview'],
    queryFn: api.getMarketOverview,
    refetchInterval: 60000, // Refresh every minute
  })
}

export function useHistoricalPrices(
  symbol: string,
  startDate?: string,
  endDate?: string
) {
  return useQuery({
    queryKey: ['historical', symbol, startDate, endDate],
    queryFn: () => api.getHistoricalPrices(symbol, startDate, endDate),
    enabled: !!symbol,
  })
}

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: api.getStats,
  })
}

export function useSystemStatus(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['system-status'],
    queryFn: api.getSystemStatus,
    staleTime: 60_000,
    refetchInterval: 120_000,
    enabled: options?.enabled ?? true,
  })
}

export function useAdminStatus(refDate?: string) {
  return useQuery({
    queryKey: ['admin-status', refDate],
    queryFn: () => api.getAdminStatus(refDate),
    staleTime: 30_000,
    refetchInterval: 60_000,
  })
}

export function useAdminHistory(startDate: string, endDate: string, exchange?: string) {
  return useQuery({
    queryKey: ['admin-history', startDate, endDate, exchange],
    queryFn: () => api.getAdminHistory(startDate, endDate, exchange),
    staleTime: 300_000,
    enabled: !!startDate && !!endDate,
  })
}

export function useAdminAnomalies(lookbackDays?: number) {
  return useQuery({
    queryKey: ['admin-anomalies', lookbackDays],
    queryFn: () => api.getAdminAnomalies(lookbackDays),
    staleTime: 120_000,
    refetchInterval: 300_000,
  })
}

export function useIntelligenceNews(params?: { hours?: number; source?: string; region?: string; language?: string; limit?: number }) {
  return useQuery({
    queryKey: ['intelligence-news', params],
    queryFn: () => api.getIntelligenceNews(params),
    staleTime: 60_000,
    refetchInterval: 120_000,
  })
}

export function useIntelligenceSignals(params?: { hours?: number; signal_type?: string; region?: string; sector?: string; limit?: number }) {
  return useQuery({
    queryKey: ['intelligence-signals', params],
    queryFn: () => api.getIntelligenceSignals(params),
    staleTime: 60_000,
    refetchInterval: 300_000,
  })
}

export function useIntelligenceSectors(params?: { region?: string }) {
  return useQuery({
    queryKey: ['intelligence-sectors', params],
    queryFn: () => api.getIntelligenceSectors(params),
    staleTime: 300_000,
    refetchInterval: 600_000,
  })
}

export function useSectorThemes(themeType?: string) {
  return useQuery({
    queryKey: ['sector-themes', themeType],
    queryFn: () => api.getSectorThemes(themeType),
    staleTime: 300_000, // 5 min — refreshed daily by scheduler
  })
}

export function useSectorThemeDetail(name: string, themeType = 'static_gics') {
  return useQuery({
    queryKey: ['sector-theme-detail', name, themeType],
    queryFn: () => api.getSectorThemeDetail(name, themeType),
    enabled: !!name,
    staleTime: 300_000,
  })
}

export function useStockRelationships(symbol: string) {
  return useQuery({
    queryKey: ['stock-relationships', symbol],
    queryFn: () => api.getStockRelationships(symbol),
    enabled: !!symbol,
    staleTime: 3_600_000, // 1h — computed weekly
  })
}

// Per-symbol market-data panels (all refreshed weekly on the collector).
export function useInsiderActivity(symbol: string) {
  return useQuery({
    queryKey: ['insider', symbol], queryFn: () => api.getInsiderActivity(symbol),
    enabled: !!symbol, staleTime: 3_600_000,
  })
}
export function useShortInterest(symbol: string) {
  return useQuery({
    queryKey: ['short-interest', symbol], queryFn: () => api.getShortInterest(symbol),
    enabled: !!symbol, staleTime: 3_600_000,
  })
}
export function useCongressTrades(symbol: string) {
  return useQuery({
    queryKey: ['congress', symbol], queryFn: () => api.getCongressTrades(symbol),
    enabled: !!symbol, staleTime: 3_600_000,
  })
}
export function useFilings(symbol: string) {
  return useQuery({
    queryKey: ['filings', symbol], queryFn: () => api.getFilings(symbol),
    enabled: !!symbol, staleTime: 3_600_000,
  })
}

export function useShowcaseStocks(params?: { exchanges?: string[]; sector?: string }) {
  return useQuery({
    queryKey: ['showcase', params],
    queryFn: () => api.getShowcaseStocks(params),
    staleTime: 60_000,
  })
}

export function useAlerts(enabled = true) {
  const qc = useQueryClient()

  const query = useQuery({
    queryKey: ['user-alerts'],
    queryFn: api.getAlerts,
    enabled,
    staleTime: 30_000,
  })

  const createAlert = async (symbol: string, alert_type: AlertType, threshold: number) => {
    await api.createAlert(symbol, alert_type, threshold)
    qc.invalidateQueries({ queryKey: ['user-alerts'] })
  }

  const deleteAlert = async (id: number) => {
    await api.deleteAlert(id)
    qc.invalidateQueries({ queryKey: ['user-alerts'] })
  }

  const rearmAlert = async (id: number) => {
    await api.rearmAlert(id)
    qc.invalidateQueries({ queryKey: ['user-alerts'] })
  }

  return { ...query, createAlert, deleteAlert, rearmAlert }
}
