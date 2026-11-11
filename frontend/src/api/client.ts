import axios from 'axios'
import keycloak from '../auth/keycloak'

const API_BASE = '/api/v1'

/**
 * Normalize a FastAPI error response to a human-readable string.
 *
 * FastAPI's HTTPException sets a `detail` field that is normally a string,
 * but we use structured objects ({ code, message, ... }) for some endpoints
 * (e.g. symbol-not-found with suggestions). This helper unwraps either form.
 */
function extractErrorMessage(errBody: unknown, fallback: string): string {
  const detail = (errBody as { detail?: unknown } | null | undefined)?.detail
  if (typeof detail === 'string' && detail.length > 0) return detail
  if (detail && typeof detail === 'object') {
    const message = (detail as { message?: unknown }).message
    if (typeof message === 'string' && message.length > 0) return message
  }
  return fallback
}

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  paramsSerializer: {
    serialize: (params) => {
      const searchParams = new URLSearchParams()
      for (const [key, value] of Object.entries(params)) {
        if (Array.isArray(value)) {
          value.forEach((v) => searchParams.append(key, v))
        } else if (value !== undefined && value !== null) {
          searchParams.append(key, String(value))
        }
      }
      return searchParams.toString()
    },
  },
})

// Refresh token if it expires within 30 s, then attach it as Bearer.
// For anonymous users, skip entirely — public API endpoints work without auth.
apiClient.interceptors.request.use(async (config) => {
  if (!keycloak.authenticated) return config
  try {
    await keycloak.updateToken(30)
  } catch {
    keycloak.login()
    return Promise.reject(new Error('Session expired — redirecting to login'))
  }
  if (keycloak.token) {
    config.headers.Authorization = `Bearer ${keycloak.token}`
  }
  return config
})

// Types
export interface Stock {
  id: number
  symbol: string
  name: string
  name_cn: string | null | undefined
  exchange: string | null | undefined
  currency: string | null | undefined
  sector: string | null | undefined
  industry: string | null | undefined
  market_cap: number | null | undefined
  price: number | null | undefined
  change: number | null | undefined
  change_percent: number | null | undefined
  volume: number | null | undefined
  quote_timestamp: string | null | undefined
}

/**
 * Return the display name for a stock based on the active locale.
 * When locale is Chinese and a Chinese name exists, returns name_cn.
 * Otherwise falls back to the English name.
 */
export function resolveStockName(
  name: string,
  name_cn: string | null | undefined,
  language: string,
): string {
  if (language === 'zh' && name_cn) return name_cn
  return name
}

export interface Quote {
  id: number
  stock_id: number
  symbol: string
  name: string
  price: number
  open_price: number | null | undefined
  high: number | null | undefined
  low: number | null | undefined
  close: number | null | undefined
  volume: number | null | undefined
  change: number | null | undefined
  change_percent: number | null | undefined
  timestamp: string
}

export interface HistoricalPrice {
  date: string
  open_price: number | null | undefined
  high: number | null | undefined
  low: number | null | undefined
  close: number | null | undefined
  adj_close: number | null | undefined
  volume: number | null | undefined
}

export interface MarketOverview {
  indices: IndexQuote[]
  top_gainers: MoverStock[]
  top_losers: MoverStock[]
  most_active: MoverStock[]
  last_updated: string
}

export interface IndexQuote {
  symbol: string
  name: string
  price: number
  change: number | null | undefined
  change_percent: number | null | undefined
}

export interface MoverStock {
  symbol: string
  name: string
  name_cn: string | null | undefined
  price: number
  change: number | null | undefined
  change_percent: number | null | undefined
  volume: number | null | undefined
}

export interface SearchResult {
  symbol: string
  name: string
  name_cn: string | null | undefined
  exchange: string | null | undefined
}

export interface UserProfile {
  keycloak_id: string
  default_exchange: string | null
  default_currency: string | null
  timezone: string | null
  locale: string | null
  bio: string | null
}

export interface UserProfileUpdate {
  default_exchange?: string | null
  default_currency?: string | null
  timezone?: string | null
  locale?: string | null
  bio?: string | null
}

export interface UserAccount {
  username: string
  email: string | null
  firstName: string | null
  lastName: string | null
  avatar: string | null
}

export interface UserAccountUpdate {
  email?: string | null
  firstName?: string | null
  lastName?: string | null
  avatar?: string | null
}

export interface WatchlistResponse {
  symbols: string[]
}

export interface NewsItem {
  id: number
  source: string
  source_id: string | null
  title: string
  summary: string | null
  url: string | null
  published_at: string
  region: string | null
  language: string
  raw_sentiment: number | null
  is_processed: boolean
}

export interface MarketSignalItem {
  id: number
  news_item_id: number
  signal_type: string
  sentiment: number | null
  confidence: number | null
  impact_horizon: string | null
  regions: string[]
  sectors_affected: string[]
  symbols_mentioned: string[]
  symbols_impacted: string[]
  theme_tags: string[]
  summary_en: string | null
  summary_zh: string | null
  processed_at: string
  model_used: string | null
}

export interface SectorIntelligenceItem {
  id: number
  sector: string
  region: string
  intel_date: string
  signal_count: number
  avg_sentiment: number | null
  bullish_count: number
  bearish_count: number
  top_themes: string[]
  narrative?: string | null
  key_signal_ids?: number[] | null
  updated_at?: string | null
}

export interface SectorTheme {
  id: number
  name: string
  name_cn: string | null
  theme_type: 'static_gics' | 'dynamic_ai'
  icon_key: string | null
  stock_count: number
  avg_sentiment: number | null
  top_symbols: string[]
  top_themes: string[]
  region: string
  updated_at: string | null
}

export interface SectorThemeDetail extends SectorTheme {
  description: string | null
  description_cn: string | null
  stocks: {
    symbol: string
    name: string
    name_cn: string | null
    exchange: string | null
    market_cap: number | null
    price: number | null
    change: number | null
    change_percent: number | null
  }[]
}

export interface StockRelationship {
  symbol: string
  relationship_type: string
  strength: number | null
  correlation_30d: number | null
  correlation_90d: number | null
  direction: 'positive' | 'negative' | null
  source: string
  computed_at: string | null
}

// User alerts
export type AlertType = 'price_above' | 'price_below' | 'change_pct_above' | 'change_pct_below'

export interface UserAlert {
  id: number
  symbol: string
  alert_type: AlertType
  threshold: number
  is_active: boolean
  triggered_at: string | null
  created_at: string
}

// LLM Chat types
export interface ChatMessagePayload {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatRequest {
  provider: string
  model: string
  mode: 'platform' | 'byok'
  messages: ChatMessagePayload[]
  symbols?: string[]
  locale?: string
  temperature?: number
  max_tokens?: number
  /** Optional native agent (skill) to run this turn as. */
  agent?: string | null
  /** Server-side conversation to persist into / resume. Server may create one. */
  conversation_id?: string | null
}

export interface LLMModel {
  id: string
  label: string
}

export interface LLMProvider {
  name: string
  models: LLMModel[]
  platform_available: boolean
}

export interface ChatQuotaInfo {
  tier: 'admin' | 'paid' | 'free'
  limit: number | null          // null = unlimited
  used: number
  trial_start: string | null
  trial_end: string | null
  trial_exhausted: boolean
  exhausted_reason: 'messages' | 'time' | null
  days_remaining: number | null // null = unlimited
}

// NOVA server-side conversation history
export interface ServerConversationSummary {
  id: string
  title: string | null
  agent: string | null
  symbols: string[] | null
  message_count: number
  updated_at: string
}
export interface ServerConversationMessage {
  role: string
  content: string | null
  tools_used: string[] | null
  created_at: string
}
export interface ServerConversationDetail extends ServerConversationSummary {
  messages: ServerConversationMessage[]
}
export interface ConversationSearchHit {
  id: string
  similarity: number
  summary: string
  when: string | null
}

// NOVA investor profile
export interface InvestorProfileInput {
  risk_tolerance?: string | null
  horizon?: string | null
  style?: string | null
  preferred_sectors?: string[] | null
  avoided_sectors?: string[] | null
  constraints?: string | null
  goals?: string | null
}
export interface InvestorProfileData extends InvestorProfileInput {
  source: string            // 'user_set' | 'distilled' | 'none'
  confidence?: number | null
  updated_at?: string | null
}

// NOVA answer feedback
export interface FeedbackInput {
  rating: number               // +1 or -1
  question?: string | null
  answer?: string | null
  agent?: string | null
  model?: string | null
  tools_used?: string[] | null
  conversation_id?: string | null
}

// API functions
export const api = {
  // Stocks
  getStocks: async (params?: { skip?: number; limit?: number; sector?: string; exchanges?: string[]; symbols?: string[] }) => {
    const { data } = await apiClient.get<Stock[]>('/stocks', { params })
    return data
  },

  getStock: async (symbol: string) => {
    const { data } = await apiClient.get<Stock>(`/stocks/${symbol}`)
    return data
  },

  searchStocks: async (query: string) => {
    const { data } = await apiClient.get<SearchResult[]>('/stocks/search', {
      params: { q: query },
    })
    return data
  },

  getSectors: async () => {
    const { data } = await apiClient.get<string[]>('/stocks/sectors')
    return data
  },

  getExchanges: async () => {
    const { data } = await apiClient.get<string[]>('/stocks/exchanges')
    return data
  },

  // Quotes
  getLatestQuotes: async (symbols?: string[]) => {
    const params = symbols ? { symbols: symbols.join(',') } : undefined
    const { data } = await apiClient.get<Quote[]>('/quotes/latest', { params })
    return data
  },

  getLatestQuote: async (symbol: string) => {
    const { data } = await apiClient.get<Quote>(`/quotes/${symbol}/latest`)
    return data
  },

  getHistoricalPrices: async (
    symbol: string,
    startDate?: string,
    endDate?: string
  ) => {
    const { data } = await apiClient.get<HistoricalPrice[]>(
      `/quotes/${symbol}/history`,
      {
        params: { start_date: startDate, end_date: endDate },
      }
    )
    return data
  },

  getMarketOverview: async () => {
    const { data } = await apiClient.get<MarketOverview>('/quotes/market/overview')
    return data
  },

  // Utilities
  getHealth: async () => {
    const { data } = await apiClient.get('/health')
    return data
  },

  getStats: async () => {
    const { data } = await apiClient.get('/stats')
    return data
  },

  getSystemStatus: async () => {
    const { data } = await apiClient.get('/status/summary')
    return data as {
      db: { stocks: number; quotes: number; historical_records: number; last_quote: string | null }
      coverage: { exchange: string; total: number; quoted_today: number; pct: number }[]
      jobs_today: { job: string; status: string; runs: number; succeeded: number; attempted: number }[]
      last_updated: string
    }
  },

  getAdminStatus: async (refDate?: string) => {
    const params = refDate ? { ref_date: refDate } : {}
    const { data } = await apiClient.get('/status/admin', { params })
    return data as {
      date: string
      summary: {
        total_active_stocks: number
        total_quotes_db: number
        total_historical_db: number
        quoted_today: number
        coverage_rate: number
        last_activity: string | null
      }
      providers: {
        provider: string
        priority: number
        attempted: number
        succeeded: number
        success_rate: number | null
        records: number
        run_count: number
        last_run: string | null
        daily_limit: number | null
        daily_used: number
        daily_remaining: number | null
        minute_limit: number | null
        minute_used: number
        is_available: boolean
      }[]
      exchanges: {
        exchange: string
        total: number
        quoted_today: number
        coverage_pct: number
        latest_historical_date: string | null
        data_lag_days: number | null
      }[]
      jobs: {
        job: string
        status: string
        runs: number
        attempted: number
        succeeded: number
        records: number
        last_run: string | null
      }[]
      blockers: { provider: string; type: string; message: string }[]
      gaps: { total_missing: number; by_exchange: Record<string, number> }
      last_updated: string
    }
  },

  getAdminHistory: async (startDate: string, endDate: string, exchange?: string) => {
    const params: Record<string, string> = { start_date: startDate, end_date: endDate }
    if (exchange) params.exchange = exchange
    const { data } = await apiClient.get('/status/history', { params })
    return data as {
      start_date: string
      end_date: string
      exchanges: string[]
      data: { date: string; exchange: string; quoted: number; total: number; coverage_pct: number }[]
    }
  },

  getAdminAnomalies: async (lookbackDays?: number) => {
    const params = lookbackDays ? { lookback_days: lookbackDays } : {}
    const { data } = await apiClient.get('/status/anomalies', { params })
    return data as {
      lookback_days: number
      anomaly_count: number
      critical_count: number
      warning_count: number
      anomalies: {
        type: string
        severity: string
        exchange: string | null
        provider: string | null
        title: string
        detail: string
      }[]
      checked_at: string
    }
  },

  // Profile
  getProfile: async () => {
    const { data } = await apiClient.get<UserProfile>('/me/profile')
    return data
  },

  updateProfile: async (body: UserProfileUpdate) => {
    const { data } = await apiClient.put<UserProfile>('/me/profile', body)
    return data
  },

  getAccount: async () => {
    const { data } = await apiClient.get<UserAccount>('/me/account')
    return data
  },

  updateAccount: async (body: UserAccountUpdate) => {
    const { data } = await apiClient.put<UserAccount>('/me/account', body)
    return data
  },

  // Watchlist
  getWatchlist: async () => {
    const { data } = await apiClient.get<WatchlistResponse>('/me/watchlist')
    return data
  },

  addToWatchlist: async (symbol: string) => {
    const { data } = await apiClient.post<WatchlistResponse>('/me/watchlist', { symbol })
    return data
  },

  removeFromWatchlist: async (symbol: string) => {
    const { data } = await apiClient.delete<WatchlistResponse>(`/me/watchlist/${symbol}`)
    return data
  },

  replaceWatchlist: async (symbols: string[]) => {
    const { data } = await apiClient.put<WatchlistResponse>('/me/watchlist', { symbols })
    return data
  },

  // Public — no auth required
  getShowcaseStocks: async (params?: { exchanges?: string[]; sector?: string }) => {
    const { data } = await apiClient.get<Stock[]>('/showcase', { params })
    return data
  },

  // Public — native agent catalog (no auth)
  getAgents: async (): Promise<{ count: number; agents: AgentInfo[] }> => {
    const { data } = await apiClient.get<{ count: number; agents: AgentInfo[] }>('/agents')
    return data
  },

  // Suggest the best-matching agent for a free-text query (or null)
  suggestAgent: async (q: string): Promise<AgentInfo | null> => {
    const { data } = await apiClient.get<{ suggested: AgentInfo | null }>('/agents/suggest', { params: { q } })
    return data.suggested
  },

  // Data tools available to custom agents (for the builder's tool-picker)
  getAgentTools: async (): Promise<{ name: string; description: string }[]> => {
    const { data } = await apiClient.get<{ tools: { name: string; description: string }[] }>('/agents/tools')
    return data.tools
  },

  // Custom agents (owner-scoped, auth required)
  getMyAgents: async (): Promise<AgentInfo[]> => {
    const { data } = await apiClient.get<{ count: number; agents: AgentInfo[] }>('/me/agents')
    return data.agents
  },
  createMyAgent: async (body: CustomAgentInput): Promise<AgentInfo> => {
    const { data } = await apiClient.post<AgentInfo>('/me/agents', body)
    return data
  },
  deleteMyAgent: async (name: string): Promise<void> => {
    await apiClient.delete(`/me/agents/${encodeURIComponent(name)}`)
  },
  createShare: async (body: { title: string; symbol?: string; content: string }): Promise<{ slug: string; path: string }> => {
    const { data } = await apiClient.post<{ slug: string; path: string }>('/share', body)
    return data
  },
  getCommunityAgents: async (): Promise<CommunityAgent[]> => {
    const { data } = await apiClient.get<{ count: number; agents: CommunityAgent[] }>('/agents/community')
    return data.agents
  },
  cloneAgent: async (sourceId: number): Promise<AgentInfo> => {
    const { data } = await apiClient.post<AgentInfo>('/me/agents/clone', { source_id: sourceId })
    return data
  },
  setAgentVisibility: async (name: string, visibility: 'public' | 'private'): Promise<AgentInfo> => {
    const { data } = await apiClient.patch<AgentInfo>(`/me/agents/${encodeURIComponent(name)}/visibility`, { visibility })
    return data
  },

  // Web Push (browser notifications)
  getVapidKey: async (): Promise<{ key: string | null }> => {
    const { data } = await apiClient.get<{ key: string | null }>('/me/push/key')
    return data
  },
  getPushStatus: async (): Promise<{ enabled: boolean; subscribed: boolean; devices: number }> => {
    const { data } = await apiClient.get<{ enabled: boolean; subscribed: boolean; devices: number }>('/me/push')
    return data
  },
  subscribePush: async (body: { endpoint: string; keys: { p256dh: string; auth: string } }): Promise<void> => {
    await apiClient.post('/me/push/subscribe', body)
  },
  unsubscribePush: async (endpoint: string): Promise<void> => {
    await apiClient.post('/me/push/unsubscribe', { endpoint })
  },
  testPush: async (): Promise<{ sent: number }> => {
    const { data } = await apiClient.post<{ sent: number }>('/me/push/test')
    return data
  },
  getNotificationPrefs: async (): Promise<NotificationPrefs> => {
    const { data } = await apiClient.get<NotificationPrefs>('/me/notification-prefs')
    return data
  },
  updateNotificationPrefs: async (body: NotificationPrefs): Promise<NotificationPrefs> => {
    const { data } = await apiClient.put<NotificationPrefs>('/me/notification-prefs', body)
    return data
  },

  // Scheduled agents (Phase F4)
  getCalendarEvents: async (params?: { from?: string; to?: string; kind?: string; symbol?: string; symbols?: string; limit?: number }): Promise<{ from: string; to: string; count: number; events: CalendarEvent[] }> => {
    const { data } = await apiClient.get('/calendar/events', { params })
    return data
  },
  getUpcomingEvents: async (symbol: string): Promise<UpcomingEvents> => {
    const { data } = await apiClient.get<UpcomingEvents>(`/calendar/upcoming/${encodeURIComponent(symbol)}`)
    return data
  },
  getEntitlements: async (): Promise<Entitlements> => {
    const { data } = await apiClient.get<Entitlements>('/me/entitlements')
    return data
  },
  getMySchedules: async (): Promise<AgentSchedule[]> => {
    const { data } = await apiClient.get<{ count: number; schedules: AgentSchedule[] }>('/me/schedules')
    return data.schedules
  },
  createSchedule: async (body: ScheduleInput): Promise<AgentSchedule> => {
    const { data } = await apiClient.post<AgentSchedule>('/me/schedules', body)
    return data
  },
  updateSchedule: async (id: number, body: ScheduleInput): Promise<AgentSchedule> => {
    const { data } = await apiClient.put<AgentSchedule>(`/me/schedules/${id}`, body)
    return data
  },
  deleteSchedule: async (id: number): Promise<void> => {
    await apiClient.delete(`/me/schedules/${id}`)
  },

  // LLM Chat
  getChatProviders: async () => {
    const { data } = await apiClient.get<LLMProvider[]>('/chat/providers')
    return data
  },

  getChatQuota: async (): Promise<ChatQuotaInfo> => {
    const { data } = await apiClient.get<ChatQuotaInfo>('/chat/quota')
    return data
  },

  validateApiKey: async (provider: string, apiKey: string): Promise<{ valid: boolean | null; messageCode: string }> => {
    const { data } = await apiClient.post<{ valid: boolean | null; message_code: string }>('/chat/validate-key', {
      provider,
      api_key: apiKey,
    })
    return { valid: data.valid, messageCode: data.message_code }
  },

  // NOVA conversation history (server-side, cross-device)
  listConversations: async (): Promise<ServerConversationSummary[]> => {
    const { data } = await apiClient.get<ServerConversationSummary[]>('/me/conversations')
    return data
  },
  getServerConversation: async (id: string): Promise<ServerConversationDetail> => {
    const { data } = await apiClient.get<ServerConversationDetail>(`/me/conversations/${id}`)
    return data
  },
  searchMyConversations: async (q: string, limit = 10): Promise<ConversationSearchHit[]> => {
    const { data } = await apiClient.get<ConversationSearchHit[]>('/me/conversations/search', { params: { q, limit } })
    return data
  },
  deleteServerConversation: async (id: string): Promise<void> => {
    await apiClient.delete(`/me/conversations/${id}`)
  },
  renameServerConversation: async (id: string, title: string): Promise<void> => {
    await apiClient.patch(`/me/conversations/${id}`, { title })
  },

  // NOVA investor profile (personalization)
  getInvestorProfile: async (): Promise<InvestorProfileData> => {
    const { data } = await apiClient.get<InvestorProfileData>('/me/investor-profile')
    return data
  },
  setInvestorProfile: async (profile: InvestorProfileInput): Promise<InvestorProfileData> => {
    const { data } = await apiClient.put<InvestorProfileData>('/me/investor-profile', profile)
    return data
  },

  // NOVA answer feedback (👍/👎)
  submitFeedback: async (f: FeedbackInput): Promise<void> => {
    await apiClient.post('/me/feedback', f)
  },

  // Client-side error reporting — never throws; errors must not cause more errors
  reportClientError: async (errorType: string, message: string, context?: string): Promise<void> => {
    try {
      await apiClient.post('/me/errors', { error_type: errorType, message, context })
    } catch { /* noop */ }
  },

  // Intelligence
  getIntelligenceNews: async (params?: { hours?: number; source?: string; region?: string; language?: string; limit?: number }) => {
    const { data } = await apiClient.get<NewsItem[]>('/intelligence/news', { params })
    return data
  },

  getIntelligenceSignals: async (params?: { hours?: number; signal_type?: string; region?: string; sector?: string; limit?: number }) => {
    const { data } = await apiClient.get<MarketSignalItem[]>('/intelligence/signals', { params })
    return data
  },

  getIntelligenceSectors: async (params?: { region?: string }) => {
    const { data } = await apiClient.get<SectorIntelligenceItem[]>('/intelligence/sectors', { params })
    return data
  },

  getIntelligenceSectorDetail: async (name: string, region = 'US') => {
    const { data } = await apiClient.get<SectorIntelligenceItem>(
      `/intelligence/sector/${encodeURIComponent(name)}`,
      { params: { region } },
    )
    return data
  },

  // Sectors
  getSectorThemes: async (themeType?: string) => {
    const { data } = await apiClient.get<SectorTheme[]>('/sectors/themes', {
      params: themeType ? { theme_type: themeType } : undefined,
    })
    return data
  },

  getSectorThemeDetail: async (name: string, themeType = 'static_gics') => {
    const { data } = await apiClient.get<SectorThemeDetail>(
      `/sectors/themes/${encodeURIComponent(name)}`,
      { params: { theme_type: themeType } },
    )
    return data
  },

  getStockRelationships: async (symbol: string) => {
    const { data } = await apiClient.get<StockRelationship[]>(
      `/sectors/relationships/${symbol}`,
    )
    return data
  },

  // Per-symbol market-data panels (insider / short interest / congress / filings)
  getInsiderActivity: async (symbol: string): Promise<InsiderActivity> =>
    (await apiClient.get<InsiderActivity>(`/stocks/${symbol}/insider`)).data,
  getShortInterest: async (symbol: string): Promise<ShortInterestData> =>
    (await apiClient.get<ShortInterestData>(`/stocks/${symbol}/short-interest`)).data,
  getCongressTrades: async (symbol: string): Promise<CongressTradesData> =>
    (await apiClient.get<CongressTradesData>(`/stocks/${symbol}/congress`)).data,
  getFilings: async (symbol: string): Promise<FilingsData> =>
    (await apiClient.get<FilingsData>(`/stocks/${symbol}/filings`)).data,

  // --- Trading simulator (/me/sim) ---
  listSimAccounts: async (): Promise<SimAccountSummary[]> =>
    (await apiClient.get<SimAccountSummary[]>('/me/sim/accounts')).data,
  createSimAccount: async (b: { name: string; currency: string; initial_balance: string }): Promise<SimAccountSummary> =>
    (await apiClient.post<SimAccountSummary>('/me/sim/accounts', b)).data,
  getSimAccount: async (id: number): Promise<SimAccountValuation> =>
    (await apiClient.get<SimAccountValuation>(`/me/sim/accounts/${id}`)).data,
  resetSimAccount: async (id: number, initial_balance?: string): Promise<SimAccountSummary> =>
    (await apiClient.post<SimAccountSummary>(`/me/sim/accounts/${id}/reset`, { initial_balance: initial_balance ?? null })).data,
  deleteSimAccount: async (id: number): Promise<void> => { await apiClient.delete(`/me/sim/accounts/${id}`) },
  placeSimOrder: async (id: number, input: SimOrderInput): Promise<SimOrder> =>
    (await apiClient.post<SimOrder>(`/me/sim/accounts/${id}/orders`, input)).data,
  listSimOrders: async (id: number, status?: string): Promise<SimOrder[]> =>
    (await apiClient.get<SimOrder[]>(`/me/sim/accounts/${id}/orders`, { params: status ? { status } : {} })).data,
  cancelSimOrder: async (id: number, oid: number): Promise<SimOrder> =>
    (await apiClient.delete<SimOrder>(`/me/sim/accounts/${id}/orders/${oid}`)).data,
  getSimSnapshots: async (id: number): Promise<SimSnapshotPt[]> =>
    (await apiClient.get<SimSnapshotPt[]>(`/me/sim/accounts/${id}/snapshots`)).data,
  searchTradable: async (id: number, q: string): Promise<TradableStock[]> =>
    (await apiClient.get<TradableStock[]>(`/me/sim/accounts/${id}/tradable`, { params: { q } })).data,

  // Alerts
  getAlerts: async () => {
    const { data } = await apiClient.get<UserAlert[]>('/me/alerts')
    return data
  },

  createAlert: async (symbol: string, alert_type: AlertType, threshold: number) => {
    const { data } = await apiClient.post<UserAlert>('/me/alerts', { symbol, alert_type, threshold })
    return data
  },

  deleteAlert: async (id: number) => {
    await apiClient.delete(`/me/alerts/${id}`)
  },

  rearmAlert: async (id: number) => {
    const { data } = await apiClient.patch<UserAlert>(`/me/alerts/${id}/rearm`)
    return data
  },

  createCheckoutSession: async (priceId: string, keycloakRole: string): Promise<string> => {
    const origin = window.location.origin
    const { data } = await apiClient.post<{ checkout_url: string }>('/payments/checkout', {
      price_id: priceId,
      keycloak_role: keycloakRole,
      success_url: `${origin}/pricing?upgraded=1`,
      cancel_url: `${origin}/pricing`,
    })
    return data.checkout_url
  },
}

// A NOVA agent (skill) — native (catalog) or a user's custom agent.
export interface AgentInfo {
  name: string
  title: string
  category: string
  description: string
  tools: string[]
  model_tier: string
  example_prompts: string[]
  maturity: string
  icon: string
  custom?: boolean
  visibility?: string
  clone_count?: number
}

// A public, user-published agent in the community catalog.
export interface CommunityAgent {
  id: number
  title: string
  category: string
  description: string | null
  tools: string[]
  model_tier: string
  icon: string
  clone_count: number
}

// Payload to create a custom agent.
export interface CustomAgentInput {
  name: string
  title: string
  category?: string
  description?: string
  system_prompt: string
  tools: string[]
  model_tier: string
  icon?: string
  visibility?: string
}

export interface CalendarEvent {
  symbol: string
  name: string | null
  kind: 'earnings' | 'dividend'
  event_date: string
  time_of_day: string | null
  eps_estimate: number | null
  eps_actual: number | null
  revenue_estimate: number | null
  revenue_actual: number | null
  fiscal_period: string | null
  amount: number | null
  currency: string | null
  pay_date: string | null
  record_date: string | null
  frequency: string | null
}

export interface UpcomingEvents {
  symbol: string
  next_earnings: CalendarEvent | null
  next_dividend: CalendarEvent | null
}

export interface Entitlements {
  tier: string
  tier_label: string
  limits: { custom_agents: number; schedules: number }
  usage: { custom_agents: number; schedules: number }
}

export interface NotificationPrefs {
  push_alerts: boolean
  push_volume: boolean
  push_signals: boolean
  push_agent: boolean
  push_events: boolean
  proactive_digest: boolean
  quiet_enabled: boolean
  quiet_start: number
  quiet_end: number
  tz: string
}

export interface AgentSchedule {
  id: number
  agent_name: string
  agent_title: string
  prompt: string
  symbols: string[]
  cadence: string
  weekday: number | null
  hour: number
  minute: number
  tz: string
  is_active: boolean
  last_run_at: string | null
  last_status: string | null
}

export interface ScheduleInput {
  agent_name: string
  prompt: string
  symbols?: string[]
  cadence: string
  weekday?: number | null
  hour: number
  minute: number
  tz: string
  is_active?: boolean
}

// An inline chart NOVA renders in a chat answer (via the render_chart tool).
export interface ChartSpec {
  kind: 'price'
  normalized: boolean
  days: number
  series: { symbol: string; points: [string, number][] }[]
}

// A gated write-action NOVA proposes; the user confirms it in the chat UI.
export interface ActionProposal {
  action: 'create_alert' | 'add_to_watchlist' | 'record_trade' | 'sim_order'
  label: string
  args: Record<string, unknown>
}

// Trust layer: verifiable provenance for a fact NOVA used (which source, as of when).
export interface Source {
  tool: string
  source?: string
  as_of?: string
  symbol?: string
}

// Per-symbol market-data panel shapes (mirror the ToolRegistry handler outputs).
export interface InsiderActivity {
  symbol: string
  window_days?: number
  count?: number
  summary?: {
    open_market_buy_shares: number
    open_market_buy_value: number
    open_market_sell_shares: number
    open_market_sell_value: number
    net_open_market_shares: number
    as_of: string | null
  }
  recent?: Array<{
    date: string | null; insider: string; title: string | null; role: string | null
    code: string | null; acquired_disposed: string | null
    shares: number | null; price: number | null; value: number | null
  }>
  note?: string
}
export interface ShortInterestData {
  symbol: string
  as_of?: string | null
  short_pct_float?: number | null
  days_to_cover?: number | null
  shares_short?: number | null
  shares_short_prior_month?: number | null
  shares_short_change_pct?: number | null
  source?: string
  note?: string
}
export interface CongressTradesData {
  symbol: string
  count?: number
  buys?: number
  sells?: number
  trades?: Array<{
    transaction_date: string | null; disclosure_date: string | null
    politician: string; chamber: string; type: string | null; amount: string | null
  }>
  source?: string
  note?: string
}
export interface FilingsData {
  symbol: string
  count: number
  filings: Array<{
    form: string; filing_date: string | null; period_end: string | null
    title: string | null; url: string | null
  }>
}

// Trading simulator shapes (mirror /me/sim/* responses).
export interface SimAccountSummary {
  id: number; name: string; currency: string
  cash_balance: string; initial_balance: string
  is_active: boolean; created_at: string | null
}
export interface SimPositionView {
  symbol: string; quantity: string; avg_cost: string; price: string | null
  market_value: string; unrealized_pnl: string; unrealized_pnl_pct: number
  weight_pct: number; as_of: string | null
}
export interface SimAccountValuation {
  id: number; name: string; currency: string
  cash_balance: string; initial_balance: string; positions_value: string; equity: string
  total_return: string; total_return_pct: number
  day_change: string; day_change_pct: number
  positions: SimPositionView[]
}
export interface SimOrder {
  id: number; symbol: string; side: string; order_type: string; quantity: string
  limit_price: string | null; tif: string; status: string
  filled_quantity: string; avg_fill_price: string | null; reject_reason: string | null
  created_at: string | null; filled_at: string | null
}
export interface SimSnapshotPt { ts: string; equity: string }
export interface TradableStock { symbol: string; name: string; exchange: string | null }
export interface SimOrderInput {
  symbol: string; side: string; order_type: string
  quantity: string | number; limit_price?: string | number | null
  tif?: string; idempotency_key?: string | null
}

// SSE streaming chat — returns a ReadableStream of string chunks (delta values)
// Caller provides the auth header via getAuthHeader()
export async function streamChat(
  request: ChatRequest,
  getAuthHeader: () => string | null,
  getApiKeyHeader: () => string | null,
  onChunk: (delta: string, finishReason: string | null) => void,
  onError: (err: string) => void,
  onDone: () => void,
  onStatus?: (status: string, clearContent: boolean) => void,
  onActionProposal?: (proposal: ActionProposal) => void,
  onToolsUsed?: (tools: string[]) => void,
  onChart?: (chart: ChartSpec) => void,
  onConversation?: (id: string) => void,
  onAgentAuto?: (name: string, title: string) => void,
  onSources?: (sources: Source[]) => void,
) {
  const authHeader = getAuthHeader()
  if (!authHeader) {
    onError('Not authenticated')
    return
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${authHeader}`,
  }
  const apiKeyHeader = getApiKeyHeader()
  if (apiKeyHeader) headers['X-LLM-Api-Key'] = apiKeyHeader

  try {
    const response = await fetch('/api/v1/chat', {
      method: 'POST',
      headers,
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: response.statusText }))
      onError(extractErrorMessage(err, `HTTP ${response.status}`))
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      onError('No response body')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? '' // keep incomplete line in buffer

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (data === '[DONE]') {
          onDone()
          return
        }
        try {
          const parsed = JSON.parse(data)
          if (parsed.error) {
            // Prefer the machine-readable code; fall back to raw string
            onError(parsed.error_code ?? parsed.error)
            return
          }
          if (parsed.type === 'conversation' && onConversation) {
            onConversation(parsed.id as string)
          } else if (parsed.type === 'agent_auto' && onAgentAuto) {
            onAgentAuto(parsed.name as string, parsed.title as string)
          } else if (parsed.type === 'action_proposal' && onActionProposal) {
            onActionProposal(parsed as ActionProposal)
          } else if (parsed.type === 'tools_used' && onToolsUsed) {
            onToolsUsed(parsed.tools ?? [])
          } else if (parsed.type === 'sources' && onSources) {
            onSources((parsed.sources ?? []) as Source[])
          } else if (parsed.type === 'chart' && onChart) {
            onChart(parsed.chart as ChartSpec)
          } else if (parsed.status !== undefined && onStatus) {
            onStatus(parsed.status, parsed.clear_content === true)
          } else if (parsed.delta !== undefined) {
            onChunk(parsed.delta, parsed.finish_reason)
          }
        } catch {
          // skip malformed JSON
        }
      }
    }

    onDone()
  } catch (err) {
    onError(err instanceof Error ? err.message : 'Network error')
  }
}

// ---------------------------------------------------------------------------
// AI Insights streaming helpers
// ---------------------------------------------------------------------------

export function streamStockAnalysis(
  symbol: string,
  locale: string,
  onChunk: (delta: string) => void,
  onError: (err: string) => void,
  onDone: () => void,
) {
  return _streamAiEndpointWithBody(`/api/v1/ai/analyze/${encodeURIComponent(symbol)}`, { locale }, onChunk, onError, onDone)
}

export function streamMorningBrief(
  locale: string,
  onChunk: (delta: string) => void,
  onError: (err: string) => void,
  onDone: () => void,
) {
  return _streamAiEndpointWithBody('/api/v1/ai/brief', { locale }, onChunk, onError, onDone)
}

export function streamCompare(
  symbols: string[],
  locale: string,
  onChunk: (delta: string) => void,
  onError: (err: string) => void,
  onDone: () => void,
) {
  return _streamAiEndpointWithBody('/api/v1/ai/compare', { symbols, locale }, onChunk, onError, onDone)
}

export function streamMacroImpact(
  event: string,
  locale: string,
  onChunk: (delta: string) => void,
  onError: (err: string) => void,
  onDone: () => void,
) {
  return _streamAiEndpointWithBody('/api/v1/ai/macro-impact', { event, locale }, onChunk, onError, onDone)
}

export function streamCommittee(
  symbol: string,
  locale: string,
  onChunk: (delta: string) => void,
  onError: (err: string) => void,
  onDone: () => void,
) {
  return _streamAiEndpointWithBody(`/api/v1/ai/committee/${encodeURIComponent(symbol)}`, { locale }, onChunk, onError, onDone)
}

export function streamStrategy(
  symbol: string,
  strategy: string,
  locale: string,
  onChunk: (delta: string) => void,
  onError: (err: string) => void,
  onDone: () => void,
) {
  return _streamAiEndpointWithBody('/api/v1/ai/strategy', { symbol, strategy, locale }, onChunk, onError, onDone)
}

export function streamPortfolioAnalysis(
  locale: string,
  onChunk: (delta: string) => void,
  onError: (err: string) => void,
  onDone: () => void,
) {
  return _streamAiEndpointWithBody('/api/v1/ai/portfolio/analyze', { locale }, onChunk, onError, onDone)
}

// POST-based SSE streaming helper (with JSON body)
async function _streamAiEndpointWithBody(
  url: string,
  body: unknown,
  onChunk: (delta: string) => void,
  onError: (err: string) => void,
  onDone: () => void,
) {
  if (!keycloak.authenticated) { onError('Not authenticated'); return }
  try { await keycloak.updateToken(30) } catch { keycloak.login(); return }
  const token = keycloak.token
  if (!token) { onError('No token'); return }

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: response.statusText }))
      onError(extractErrorMessage(err, `HTTP ${response.status}`))
      return
    }
    const reader = response.body?.getReader()
    if (!reader) { onError('No response body'); return }
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (data === '[DONE]') { onDone(); return }
        try {
          const parsed = JSON.parse(data)
          if (parsed.error || parsed.type === 'error') { onError(parsed.content || parsed.error); return }
          if (parsed.delta !== undefined) onChunk(parsed.delta)
        } catch { /* skip malformed */ }
      }
    }
    onDone()
  } catch (err) {
    onError(err instanceof Error ? err.message : 'Network error')
  }
}

// ── Screen stocks (non-streaming, JSON response) ──────────────────────────────

export interface ScreenResult {
  symbol: string
  name: string
  exchange: string | null
  sector: string | null
  price: number | null
  change_pct: number | null
  market_cap: number | null
}

export interface ScreenResponse {
  query: string
  filters: Record<string, unknown>
  results: ScreenResult[]
  count: number
}

export async function screenStocks(query: string): Promise<ScreenResponse> {
  if (!keycloak.authenticated) throw new Error('Not authenticated')
  await keycloak.updateToken(30)
  const token = keycloak.token
  if (!token) throw new Error('No token')

  const response = await fetch('/api/v1/ai/screen', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(extractErrorMessage(err, `HTTP ${response.status}`))
  }
  return response.json()
}

// ── Shadow Portfolio REST helpers ─────────────────────────────────────────────

export interface ShadowTrade {
  id: number
  symbol: string
  action: string
  shares: number
  price: number
  note: string | null
  trade_date: string
  created_at: string
}

export interface TradeInput {
  symbol: string
  action: string
  shares: number
  price: number
  note?: string | null
  trade_date?: string | null
}

export async function addShadowTrade(trade: TradeInput): Promise<ShadowTrade> {
  const { data } = await apiClient.post<ShadowTrade>('/ai/portfolio/trades', trade)
  return data
}

export async function listShadowTrades(): Promise<ShadowTrade[]> {
  const { data } = await apiClient.get<ShadowTrade[]>('/ai/portfolio/trades')
  return data
}

export async function deleteShadowTrade(tradeId: number): Promise<void> {
  await apiClient.delete(`/ai/portfolio/trades/${tradeId}`)
}
