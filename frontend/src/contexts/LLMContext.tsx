import {
  createContext,
  useState,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  startTransition,
  type ReactNode,
} from 'react'
import {
  api,
  streamChat,
  streamStockAnalysis,
  streamCompare,
  streamMacroImpact,
  streamCommittee,
  streamStrategy,
  streamPortfolioAnalysis,
  screenStocks,
  type LLMProvider as APILLMProvider,
  type ActionProposal,
  type ChartSpec,
  type Source,
} from '../api/client'
import keycloak from '../auth/keycloak'
import i18n from '../i18n'
import { lsSet, lsGet, lsRemove } from '../utils/storage'
import {
  type LLMMode,
  type LLMProviderName,
  type LLMProviderMeta,
  LLM_PROVIDERS,
} from './llmProviders'

// Re-export types so existing imports from this module continue to work
export type { LLMMode, LLMProviderName, LLMProviderMeta }

/**
 * Map a raw error string to a user-friendly i18n message.
 * Raw HTTP codes and stack traces must never reach the UI.
 */
function classifyError(err: string): string {
  // Structured codes from backend — exact match first
  if (err === 'quota_exhausted') return i18n.t('chat.errorQuotaExhausted')
  if (err === 'rate_limit') return i18n.t('chat.errorRateLimit')
  if (err === 'auth_error') return i18n.t('chat.errorAuth')
  if (err === 'context_too_long') return i18n.t('chat.errorContextTooLong')
  if (err === 'provider_unavailable') return i18n.t('chat.errorProviderUnavailable')
  if (err === 'transient') return i18n.t('chat.errorTransient')

  // Fallback: keyword matching for raw network/pre-stream errors
  const lower = err.toLowerCase()
  if (lower.includes('insufficient_quota') || lower.includes('exceeded your current quota')) return i18n.t('chat.errorQuotaExhausted')
  if (lower.includes('429') || lower.includes('rate limit')) return i18n.t('chat.errorRateLimit')
  if (lower.includes('context') && lower.includes('window')) return i18n.t('chat.errorContextTooLong')
  if (lower.includes('401') || lower.includes('403') || lower.includes('unauthorized') || lower.includes('rejected') || lower.includes('api key')) return i18n.t('chat.errorAuth')
  return i18n.t('chat.errorTransient')
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  isError?: boolean
  /** Gated write-actions NOVA proposed; rendered as confirm cards. */
  actions?: ActionProposal[]
  /** Data tools NOVA used to answer; rendered as a citations chip row. */
  toolsUsed?: string[]
  /** Verifiable provenance (source + as-of) for the data NOVA used. */
  sources?: Source[]
  /** Inline charts NOVA rendered (via render_chart). */
  charts?: ChartSpec[]
  /** Agent the router auto-selected for this turn (auto-dispatch). */
  autoAgent?: { name: string; title: string }
  /** User rating of this answer: +1 (👍) or -1 (👎). */
  feedback?: 1 | -1
}

export interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: string
  mode: LLMMode
  provider: LLMProviderName | null
  isFavorite?: boolean
  /** Server-side conversation id (for persistence, rolling summary, cross-device). */
  serverId?: string
}

export interface LLMModel {
  id: string
  label: string
}

export interface LLMContextValue {
  mode: LLMMode
  provider: LLMProviderName | null
  apiKey: string
  setMode: (mode: LLMMode) => void
  setProvider: (provider: LLMProviderName) => void
  setApiKey: (key: string) => void
  clearApiKey: (provider?: LLMProviderName) => void
  /** Returns all providers that have a key saved in localStorage. */
  getActivatedProviders: () => LLMProviderName[]
  /** Load API key for any provider directly from localStorage (bypasses current selection). */
  getApiKeyForProvider: (provider: LLMProviderName) => string
  /** The provider currently toggled ON for BYOK. Null means no BYOK active → falls back to platform. */
  byokActiveProvider: LLMProviderName | null
  /** Toggle a BYOK provider ON (or OFF if already active). Null deselects all. */
  setByokActive: (provider: LLMProviderName | null) => void
  /** Save an API key for a specific provider without changing the active provider. */
  saveKeyForProvider: (provider: LLMProviderName, key: string) => void
  // conversation state
  conversations: Conversation[]
  activeConversationId: string | null
  messages: ChatMessage[]
  streaming: boolean
  toolStatus: string | null   // 'fetching_data' while tools are executing, null otherwise
  sendMessage: (content: string, agentOverride?: string | null) => void
  analyzeStock: (symbol: string) => void
  newConversation: () => void
  clearMessages: () => void
  deleteConversation: (id: string) => void
  switchConversation: (id: string) => void
  /** Import a server-side conversation (from another device) into the local list
   *  and open it. Resolves to the local conversation id (or null on failure). */
  resumeServerConversation: (serverId: string) => Promise<string | null>
  clearAllConversations: () => void
  toggleFavorite: (id: string) => void
  /** Rate an assistant answer (👍/👎); persists locally + posts for evals. */
  submitFeedback: (messageId: string, rating: 1 | -1) => void
  // provider list + model
  providers: APILLMProvider[]
  selectedModel: string
  setSelectedModel: (model: string) => void
  // active native agent (skill) for the chat; null = generalist NOVA
  selectedAgent: string | null
  setSelectedAgent: (agent: string | null) => void
  // chat panel open/close state
  chatOpen: boolean
  openChat: () => void
  closeChat: () => void
  toggleChat: () => void
  // focused symbol (dashboard → chat analysis)
  focusedSymbol: string | null
  clearFocusedSymbol: () => void
  analyzeFocusedStock: (symbol: string) => void
  // new AI features
  screenStocksAction: (query: string) => void
  compareStocks: (symbols: string[]) => void
  macroImpact: (event: string) => void
  runCommittee: (symbol: string) => void
  buildStrategy: (symbol: string, strategy: string) => void
  runPortfolioAnalysis: () => void
}

// ── localStorage keys ────────────────────────────────────────────────────────

const KEY_MODE = 'FlowDesktop_llm_mode'
const KEY_PROVIDER = 'FlowDesktop_llm_provider'
const KEY_BYOK_ACTIVE = 'FlowDesktop_llm_byok_active'
const KEY_CONVERSATIONS = 'FlowDesktop_llm_conversations'
const KEY_ACTIVE_CONVERSATION = 'FlowDesktop_llm_active_conversation_id'
const keyForProvider = (p: string) => `FlowDesktop_llm_key_${p}`

function genId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

// ── localStorage helpers ─────────────────────────────────────────────────────

function loadMode(): LLMMode {
  const v = lsGet(KEY_MODE)
  return v === 'byok' ? 'byok' : 'flowdesktop'
}

function loadProvider(): LLMProviderName | null {
  return (lsGet(KEY_PROVIDER) as LLMProviderName) || null
}

function loadByokActive(): LLMProviderName | null {
  return (lsGet(KEY_BYOK_ACTIVE) as LLMProviderName) || null
}

/** API keys use lsSet/lsGet (same encoding as all other persisted values). */
function loadApiKey(provider: LLMProviderName | null): string {
  if (!provider) return ''
  return lsGet(keyForProvider(provider)) ?? ''
}

function loadConversations(): Conversation[] {
  const raw = lsGet(KEY_CONVERSATIONS)
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveConversations(convs: Conversation[]) {
  lsSet(KEY_CONVERSATIONS, JSON.stringify(convs))
}

function loadActiveConversationId(): string | null {
  return lsGet(KEY_ACTIVE_CONVERSATION)
}

function saveActiveConversationId(id: string | null) {
  if (id) lsSet(KEY_ACTIVE_CONVERSATION, id)
  else lsRemove(KEY_ACTIVE_CONVERSATION)
}

// ── Context ──────────────────────────────────────────────────────────────────

const LLMContext = createContext<LLMContextValue | null>(null)

// ── Provider ─────────────────────────────────────────────────────────────────

export function LLMProvider({ children }: { children: ReactNode }) {
  const [mode, _setMode] = useState<LLMMode>(loadMode)
  const [provider, _setProvider] = useState<LLMProviderName | null>(loadProvider)
  const [apiKey, _setApiKey] = useState<string>(() => loadApiKey(loadProvider()))
  const [byokActiveProvider, _setByokActiveProvider] = useState<LLMProviderName | null>(loadByokActive)

  const [conversations, _setConversations] = useState<Conversation[]>(loadConversations)
  const [activeConversationId, _setActiveConversationId] = useState<string | null>(loadActiveConversationId)
  const [messages, _setMessages] = useState<ChatMessage[]>([])
  const [streaming, _setStreaming] = useState(false)
  const [toolStatus, _setToolStatus] = useState<string | null>(null)
  const [providers, _setProviders] = useState<APILLMProvider[]>([])
  const [selectedModel, _setSelectedModel] = useState<string>('gpt-4o-mini')
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [chatOpen, _setChatOpen] = useState(false)
  const [focusedSymbol, _setFocusedSymbol] = useState<string | null>(null)
  // Server conversation id for the ephemeral (no active client conversation) path.
  const ephemeralServerIdRef = useRef<string | null>(null)

  const openChat   = useCallback(() => _setChatOpen(true),  [])
  const closeChat  = useCallback(() => _setChatOpen(false), [])
  const toggleChat = useCallback(() => _setChatOpen(o => !o), [])
  const clearFocusedSymbol = useCallback(() => _setFocusedSymbol(null), [])

  // Fetch provider list from backend on mount; auto-select first available if none saved
  useEffect(() => {
    api.getChatProviders()
      .then(data => {
        _setProviders(data)
        const current = data.find(p => p.name === provider)
        // In platform/flowdesktop mode the saved provider must also be platform_available.
        // In byok mode any provider is valid regardless of server key configuration.
        const currentUsable = current && (loadMode() === 'byok' || current.platform_available)
        if (currentUsable) {
          if (current!.models.length > 0) _setSelectedModel(current!.models[0].id)
        } else {
          // Saved provider not usable — auto-select first platform-available one
          const first = data.find(p => p.platform_available)
          if (first) {
            _setProvider(first.name as LLMProviderName)
            lsSet(KEY_PROVIDER, first.name)
            if (first.models.length > 0) _setSelectedModel(first.models[0].id)
          }
        }
      })
      .catch(() => { /* backend not available yet — use empty list */ })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Update selected model when provider changes
  useEffect(() => {
    const current = providers.find(p => p.name === provider)
    if (current && current.models.length > 0) {
      startTransition(() => { _setSelectedModel(current.models[0].id) })
    }
  }, [provider, providers])

  // Resolve messages from active conversation
  const resolvedMessages = useMemo(() => {
    if (activeConversationId) {
      const conv = conversations.find(c => c.id === activeConversationId)
      return conv?.messages ?? []
    }
    return messages
  }, [activeConversationId, conversations, messages])

  const setMode = useCallback((m: LLMMode) => {
    _setMode(m)
    lsSet(KEY_MODE, m)
  }, [])

  const setProvider = useCallback((p: LLMProviderName) => {
    _setProvider(p)
    _setApiKey(loadApiKey(p))
    lsSet(KEY_PROVIDER, p)
  }, [])

  const setApiKey = useCallback((key: string) => {
    _setApiKey(key)
    const p = loadProvider()
    if (p) lsSet(keyForProvider(p), key)
  }, [])

  const clearApiKey = useCallback((p?: LLMProviderName) => {
    const target = p ?? loadProvider()
    if (target) {
      lsRemove(keyForProvider(target))
    }
    if (!p || p === loadProvider()) {
      _setApiKey('')
    }
  }, [])

  const getActivatedProviders = useCallback((): LLMProviderName[] => {
    return LLM_PROVIDERS.filter(p => !!lsGet(keyForProvider(p.id))).map(p => p.id)
  }, [])

  const getApiKeyForProvider = useCallback((p: LLMProviderName): string => {
    return lsGet(keyForProvider(p)) ?? ''
  }, [])

  /** Toggle a BYOK provider ON. If already active, toggle it OFF (set to null). */
  const setByokActive = useCallback((p: LLMProviderName | null) => {
    _setByokActiveProvider(p)
    if (p) {
      lsSet(KEY_BYOK_ACTIVE, p)
      // Always persist mode='byok' so it survives logout/login
      _setMode('byok')
      lsSet(KEY_MODE, 'byok')
      // Keep provider state in sync for conversation metadata
      _setProvider(p)
      lsSet(KEY_PROVIDER, p)
      // Load the API key for this provider into the active apiKey state
      _setApiKey(loadApiKey(p))
      // Update selectedModel to this provider's first model
      const found = providers.find(pd => pd.name === p)
      if (found && found.models.length > 0) _setSelectedModel(found.models[0].id)
    } else {
      lsRemove(KEY_BYOK_ACTIVE)
    }
  }, [providers])

  /** Save an API key for a specific provider without making it the active BYOK provider. */
  const saveKeyForProvider = useCallback((p: LLMProviderName, key: string) => {
    if (key) {
      lsSet(keyForProvider(p), key)
    } else {
      lsRemove(keyForProvider(p))
    }
    // If this is the currently active BYOK provider, sync the apiKey state
    if (p === loadByokActive()) {
      _setApiKey(key)
    }
  }, [])

  const setConversationsAndSave = useCallback((convs: Conversation[]) => {
    _setConversations(convs)
    saveConversations(convs)
  }, [])

  const newConversation = useCallback(() => {
    const conv: Conversation = {
      id: genId(),
      title: '',
      messages: [],
      createdAt: new Date().toISOString(),
      mode,
      provider,
    }
    setConversationsAndSave([conv, ...conversations])
    _setActiveConversationId(conv.id)
    _setMessages([])
    saveActiveConversationId(conv.id)
    ephemeralServerIdRef.current = null
  }, [conversations, mode, provider, setConversationsAndSave])

  const clearMessages = useCallback(() => {
    if (activeConversationId) {
      const updated = conversations.map(c =>
        c.id === activeConversationId ? { ...c, messages: [] } : c
      )
      setConversationsAndSave(updated)
    }
    _setMessages([])
  }, [activeConversationId, conversations, setConversationsAndSave])

  const deleteConversation = useCallback((id: string) => {
    const updated = conversations.filter(c => c.id !== id)
    setConversationsAndSave(updated)
    if (activeConversationId === id) {
      const next = updated[0] ?? null
      _setActiveConversationId(next?.id ?? null)
      saveActiveConversationId(next?.id ?? null)
    }
  }, [conversations, activeConversationId, setConversationsAndSave])

  const switchConversation = useCallback((id: string) => {
    _setActiveConversationId(id)
    saveActiveConversationId(id)
  }, [])

  const resumeServerConversation = useCallback(async (serverId: string): Promise<string | null> => {
    // Already imported on this device? Just switch to it.
    const existing = conversations.find(c => c.serverId === serverId)
    if (existing) {
      _setActiveConversationId(existing.id)
      saveActiveConversationId(existing.id)
      ephemeralServerIdRef.current = serverId
      _setChatOpen(true)
      return existing.id
    }
    try {
      const detail = await api.getServerConversation(serverId)
      const localId = genId()
      const conv: Conversation = {
        id: localId,
        title: detail.title || '',
        createdAt: detail.updated_at || new Date().toISOString(),
        mode,
        provider,
        serverId,
        messages: detail.messages
          .filter(m => m.role === 'user' || m.role === 'assistant')
          .map(m => ({
            id: genId(),
            role: m.role as 'user' | 'assistant',
            content: m.content ?? '',
            timestamp: m.created_at,
            toolsUsed: m.tools_used ?? undefined,
          })),
      }
      setConversationsAndSave([conv, ...conversations])
      _setActiveConversationId(localId)
      saveActiveConversationId(localId)
      ephemeralServerIdRef.current = serverId
      _setChatOpen(true)
      return localId
    } catch {
      return null
    }
  }, [conversations, mode, provider, setConversationsAndSave])

  const clearAllConversations = useCallback(() => {
    setConversationsAndSave([])
    _setActiveConversationId(null)
    _setMessages([])
    saveActiveConversationId(null)
  }, [setConversationsAndSave])

  const toggleFavorite = useCallback((id: string) => {
    const updated = conversations.map(c =>
      c.id === id ? { ...c, isFavorite: !c.isFavorite } : c
    )
    setConversationsAndSave(updated)
  }, [conversations, setConversationsAndSave])

  const submitFeedback = useCallback((messageId: string, rating: 1 | -1) => {
    const list = resolvedMessages
    const idx = list.findIndex(m => m.id === messageId)
    if (idx < 0) return
    const msg = list[idx]
    let question = ''
    for (let i = idx - 1; i >= 0; i--) {
      if (list[i].role === 'user') { question = list[i].content; break }
    }
    // Optimistic local patch (persists in localStorage)
    if (activeConversationId) {
      _setConversations(prev => {
        const updated = prev.map(c =>
          c.id === activeConversationId
            ? { ...c, messages: c.messages.map(m => (m.id === messageId ? { ...m, feedback: rating } : m)) }
            : c
        )
        saveConversations(updated)
        return updated
      })
    } else {
      _setMessages(prev => prev.map(m => (m.id === messageId ? { ...m, feedback: rating } : m)))
    }
    const activeConv = activeConversationId ? conversations.find(c => c.id === activeConversationId) : null
    api.submitFeedback({
      rating,
      question,
      answer: msg.content,
      agent: msg.autoAgent?.name ?? selectedAgent,
      tools_used: msg.toolsUsed,
      model: selectedModel,
      conversation_id: activeConv?.serverId ?? ephemeralServerIdRef.current ?? null,
    }).catch(() => { /* best-effort */ })
  }, [resolvedMessages, activeConversationId, conversations, selectedAgent, selectedModel])

  const sendMessage = useCallback((content: string, agentOverride?: string | null) => {
    // agentOverride lets a caller (e.g. the Agents "Try it" deep-link) run this
    // first turn as a specific agent without waiting for the setSelectedAgent
    // state update to land — avoids a stale-closure miss on the very first send.
    const agentForTurn = agentOverride !== undefined ? agentOverride : selectedAgent
    const userMsg: ChatMessage = {
      id: genId(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    }

    // Pre-generate the assistant message ID so chunks accumulate into one message
    const assistantMsgId = genId()
    const assistantPlaceholder: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    }

    if (activeConversationId) {
      const updated = conversations.map(c =>
        c.id === activeConversationId
          ? { ...c, messages: [...c.messages, userMsg, assistantPlaceholder], title: c.title || content.slice(0, 60) }
          : c
      )
      setConversationsAndSave(updated)
    } else {
      _setMessages(prev => [...prev, userMsg, assistantPlaceholder])
    }

    _setStreaming(true)

    // Build prior messages + current user message for the API
    const chatMessages = [
      ...resolvedMessages.slice(-20).map(m => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
      })),
      { role: 'user' as const, content },
    ]

    // Accumulate each delta into the placeholder assistant message
    const handleChunk = (delta: string) => {
      if (activeConversationId) {
        _setConversations(prev => {
          const updated = prev.map(c =>
            c.id === activeConversationId
              ? {
                  ...c,
                  messages: c.messages.map(m =>
                    m.id === assistantMsgId ? { ...m, content: m.content + delta } : m
                  ),
                }
              : c
          )
          saveConversations(updated)
          return updated
        })
      } else {
        _setMessages(prev => prev.map(m =>
          m.id === assistantMsgId ? { ...m, content: m.content + delta } : m
        ))
      }
    }

    const handleDone = () => {
      _setStreaming(false)
      _setToolStatus(null)
    }

    // Apply a patch to the in-flight assistant message (works in both the
    // persisted-conversation and ephemeral-messages paths).
    const patchAssistant = (patch: (m: ChatMessage) => ChatMessage) => {
      if (activeConversationId) {
        _setConversations(prev => {
          const updated = prev.map(c =>
            c.id === activeConversationId
              ? { ...c, messages: c.messages.map(m => (m.id === assistantMsgId ? patch(m) : m)) }
              : c
          )
          saveConversations(updated)
          return updated
        })
      } else {
        _setMessages(prev => prev.map(m => (m.id === assistantMsgId ? patch(m) : m)))
      }
    }

    const handleActionProposal = (proposal: ActionProposal) => {
      patchAssistant(m => ({ ...m, actions: [...(m.actions ?? []), proposal] }))
    }

    const handleChart = (chart: ChartSpec) => {
      patchAssistant(m => ({ ...m, charts: [...(m.charts ?? []), chart] }))
    }

    const handleToolsUsed = (tools: string[]) => {
      patchAssistant(m => ({ ...m, toolsUsed: tools }))
    }

    const handleSources = (sources: Source[]) => {
      patchAssistant(m => ({ ...m, sources }))
    }

    // Server created/identified the conversation — remember its id so subsequent
    // turns persist into the same thread (enables the rolling summary + history).
    const handleConversation = (sid: string) => {
      if (activeConversationId) {
        _setConversations(prev => {
          const updated = prev.map(c =>
            c.id === activeConversationId && !c.serverId ? { ...c, serverId: sid } : c
          )
          saveConversations(updated)
          return updated
        })
      } else {
        ephemeralServerIdRef.current = sid
      }
    }

    const handleAgentAuto = (name: string, title: string) => {
      patchAssistant(m => ({ ...m, autoAgent: { name, title } }))
    }

    const handleStatus = (status: string, clearContent: boolean) => {
      _setToolStatus(status)
      if (clearContent) {
        // Wipe the pre-tool reasoning text from the assistant message
        if (activeConversationId) {
          _setConversations(prev => {
            const updated = prev.map(c =>
              c.id === activeConversationId
                ? { ...c, messages: c.messages.map(m =>
                    m.id === assistantMsgId ? { ...m, content: '' } : m
                  )}
                : c
            )
            saveConversations(updated)
            return updated
          })
        } else {
          _setMessages(prev => prev.map(m =>
            m.id === assistantMsgId ? { ...m, content: '' } : m
          ))
        }
      }
    }

    // Resolve effective mode: mode is authoritative.
    // 'byok' only if user explicitly selected the BYOK tab AND a provider is active AND has a key.
    // Switching to "Use FlowDesktop AI" tab sets mode='flowdesktop' which immediately overrides BYOK
    // without touching byokActiveProvider or the stored key (so switching back is instant).
    const byokKey = byokActiveProvider ? getApiKeyForProvider(byokActiveProvider) : ''
    const effectiveMode = (mode === 'byok' && byokActiveProvider && byokKey) ? 'byok' : 'platform'
    const effectiveProvider = (effectiveMode === 'byok' ? byokActiveProvider : null) ?? provider ?? 'openai'

    const activeConv = activeConversationId ? conversations.find(c => c.id === activeConversationId) : null
    const serverConvId = activeConv?.serverId ?? ephemeralServerIdRef.current ?? null

    streamChat(
      {
        provider: effectiveProvider,
        model: selectedModel,
        mode: effectiveMode,
        messages: chatMessages,
        agent: agentForTurn,
        locale: i18n.language,
        conversation_id: serverConvId,
      },
      () => keycloak.token ?? null,
      () => (byokKey || null) as string | null,
      handleChunk,
      err => {
        api.reportClientError('llm_stream', err, `provider=${effectiveProvider} model=${selectedModel}`)
        _setToolStatus(null)
        const friendlyMsg = classifyError(err)
        if (activeConversationId) {
          _setConversations(prev => {
            const updated = prev.map(c =>
              c.id === activeConversationId
                ? {
                    ...c,
                    messages: c.messages.map(m =>
                      m.id === assistantMsgId ? { ...m, content: friendlyMsg, isError: true } : m
                    ),
                  }
                : c
            )
            saveConversations(updated)
            return updated
          })
        } else {
          _setMessages(prev => prev.map(m =>
            m.id === assistantMsgId ? { ...m, content: friendlyMsg, isError: true } : m
          ))
        }
        _setStreaming(false)
      },
      handleDone,
      handleStatus,
      handleActionProposal,
      handleToolsUsed,
      handleChart,
      handleConversation,
      handleAgentAuto,
      handleSources,
    )
  }, [activeConversationId, conversations, selectedModel, selectedAgent, provider, mode,
      byokActiveProvider, getApiKeyForProvider, resolvedMessages, setConversationsAndSave])

  const analyzeStock = useCallback((symbol: string) => {
    const userMsg: ChatMessage = {
      id: genId(),
      role: 'user',
      content: i18n.t('commands.analyzeMsg', { symbol }),
      timestamp: new Date().toISOString(),
    }
    const assistantMsgId = genId()
    const assistantPlaceholder: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    }

    if (activeConversationId) {
      const updated = conversations.map(c =>
        c.id === activeConversationId
          ? { ...c, messages: [...c.messages, userMsg, assistantPlaceholder], title: c.title || userMsg.content.slice(0, 60) }
          : c
      )
      setConversationsAndSave(updated)
    } else {
      _setMessages(prev => [...prev, userMsg, assistantPlaceholder])
    }

    _setStreaming(true)

    const appendDelta = (delta: string) => {
      if (activeConversationId) {
        _setConversations(prev => {
          const updated = prev.map(c =>
            c.id === activeConversationId
              ? { ...c, messages: c.messages.map(m =>
                  m.id === assistantMsgId ? { ...m, content: m.content + delta } : m
                )}
              : c
          )
          saveConversations(updated)
          return updated
        })
      } else {
        _setMessages(prev => prev.map(m =>
          m.id === assistantMsgId ? { ...m, content: m.content + delta } : m
        ))
      }
    }

    const setErrorContent = (errMsg: string) => {
      if (activeConversationId) {
        _setConversations(prev => {
          const updated = prev.map(c =>
            c.id === activeConversationId
              ? { ...c, messages: c.messages.map(m =>
                  m.id === assistantMsgId ? { ...m, content: errMsg, isError: true } : m
                )}
              : c
          )
          saveConversations(updated)
          return updated
        })
      } else {
        _setMessages(prev => prev.map(m =>
          m.id === assistantMsgId ? { ...m, content: errMsg, isError: true } : m
        ))
      }
    }

    streamStockAnalysis(
      symbol,
      i18n.language,
      appendDelta,
      (err) => {
        setErrorContent(classifyError(err))
        _setStreaming(false)
      },
      () => { _setStreaming(false) },
    )
  }, [activeConversationId, conversations, setConversationsAndSave])

  const analyzeFocusedStock = useCallback((symbol: string) => {
    if (streaming) return
    _setFocusedSymbol(symbol)
    _setChatOpen(true)
    analyzeStock(symbol)
  }, [analyzeStock, streaming])

  // ── Generic streaming action helper ──────────────────────────────────────
  // Creates user + assistant messages, streams deltas into the assistant msg
  const _startStreamingAction = useCallback((userContent: string) => {
    const userMsg: ChatMessage = {
      id: genId(), role: 'user', content: userContent, timestamp: new Date().toISOString(),
    }
    const assistantMsgId = genId()
    const assistantPlaceholder: ChatMessage = {
      id: assistantMsgId, role: 'assistant', content: '', timestamp: new Date().toISOString(),
    }
    if (activeConversationId) {
      const updated = conversations.map(c =>
        c.id === activeConversationId
          ? { ...c, messages: [...c.messages, userMsg, assistantPlaceholder], title: c.title || userMsg.content.slice(0, 60) }
          : c
      )
      setConversationsAndSave(updated)
    } else {
      _setMessages(prev => [...prev, userMsg, assistantPlaceholder])
    }
    _setStreaming(true)

    const appendDelta = (delta: string) => {
      if (activeConversationId) {
        _setConversations(prev => {
          const updated = prev.map(c =>
            c.id === activeConversationId
              ? { ...c, messages: c.messages.map(m =>
                  m.id === assistantMsgId ? { ...m, content: m.content + delta } : m
                )}
              : c
          )
          saveConversations(updated)
          return updated
        })
      } else {
        _setMessages(prev => prev.map(m =>
          m.id === assistantMsgId ? { ...m, content: m.content + delta } : m
        ))
      }
    }

    const setError = (errMsg: string) => {
      if (activeConversationId) {
        _setConversations(prev => {
          const updated = prev.map(c =>
            c.id === activeConversationId
              ? { ...c, messages: c.messages.map(m =>
                  m.id === assistantMsgId ? { ...m, content: errMsg, isError: true } : m
                )}
              : c
          )
          saveConversations(updated)
          return updated
        })
      } else {
        _setMessages(prev => prev.map(m =>
          m.id === assistantMsgId ? { ...m, content: errMsg, isError: true } : m
        ))
      }
      _setStreaming(false)
    }

    const onDone = () => { _setStreaming(false) }

    return { appendDelta, setError, onDone }
  }, [activeConversationId, conversations, setConversationsAndSave])

  // Screen stocks (non-streaming)
  const screenStocksAction = useCallback((query: string) => {
    const userMsg: ChatMessage = {
      id: genId(), role: 'user',
      content: i18n.t('commands.screenMsg', { query }),
      timestamp: new Date().toISOString(),
    }
    const assistantMsgId = genId()
    const assistantPlaceholder: ChatMessage = {
      id: assistantMsgId, role: 'assistant', content: '', timestamp: new Date().toISOString(),
    }
    if (activeConversationId) {
      const updated = conversations.map(c =>
        c.id === activeConversationId
          ? { ...c, messages: [...c.messages, userMsg, assistantPlaceholder] }
          : c
      )
      setConversationsAndSave(updated)
    } else {
      _setMessages(prev => [...prev, userMsg, assistantPlaceholder])
    }
    _setStreaming(true)

    const setContent = (content: string, isError = false) => {
      if (activeConversationId) {
        _setConversations(prev => {
          const updated = prev.map(c =>
            c.id === activeConversationId
              ? { ...c, messages: c.messages.map(m =>
                  m.id === assistantMsgId ? { ...m, content, isError } : m
                )}
              : c
          )
          saveConversations(updated)
          return updated
        })
      } else {
        _setMessages(prev => prev.map(m =>
          m.id === assistantMsgId ? { ...m, content, isError } : m
        ))
      }
      _setStreaming(false)
    }

    screenStocks(query)
      .then(res => {
        if (res.count === 0) {
          setContent('No stocks matched your screen criteria. Try broadening the filters.')
          return
        }
        // Format results as markdown table
        const rows = res.results.slice(0, 15).map(r => {
          const price = r.price != null ? r.price.toFixed(2) : 'N/A'
          const chg = r.change_pct != null ? `${r.change_pct >= 0 ? '+' : ''}${r.change_pct.toFixed(1)}%` : 'N/A'
          const cap = r.market_cap != null
            ? r.market_cap >= 1e12 ? `$${(r.market_cap / 1e12).toFixed(1)}T`
              : r.market_cap >= 1e9 ? `$${(r.market_cap / 1e9).toFixed(1)}B`
              : r.market_cap >= 1e6 ? `$${(r.market_cap / 1e6).toFixed(1)}M`
              : `$${r.market_cap.toFixed(0)}`
            : 'N/A'
          return `| ${r.symbol} | ${r.name.slice(0, 25)} | ${r.exchange ?? ''} | ${price} | ${chg} | ${cap} |`
        })
        const table = [
          `**Screen Results** — ${res.count} match${res.count !== 1 ? 'es' : ''} for: *${query}*\n`,
          '| Symbol | Name | Exchange | Price | Change | Mkt Cap |',
          '|--------|------|----------|-------|--------|---------|',
          ...rows,
        ].join('\n')
        setContent(table)
      })
      .catch(err => {
        setContent(classifyError(err instanceof Error ? err.message : String(err)), true)
      })
  }, [activeConversationId, conversations, setConversationsAndSave])

  const compareStocks = useCallback((symbols: string[]) => {
    const { appendDelta, setError, onDone } = _startStreamingAction(
      i18n.t('commands.compareMsg', { symbols: symbols.join(' vs ') })
    )
    streamCompare(symbols, i18n.language, appendDelta, err => setError(classifyError(err)), onDone)
  }, [_startStreamingAction])

  const macroImpact = useCallback((event: string) => {
    const { appendDelta, setError, onDone } = _startStreamingAction(
      i18n.t('commands.macroMsg', { event })
    )
    streamMacroImpact(event, i18n.language, appendDelta, err => setError(classifyError(err)), onDone)
  }, [_startStreamingAction])

  const runCommittee = useCallback((symbol: string) => {
    const { appendDelta, setError, onDone } = _startStreamingAction(
      i18n.t('commands.committeeMsg', { symbol })
    )
    streamCommittee(symbol, i18n.language, appendDelta, err => setError(classifyError(err)), onDone)
  }, [_startStreamingAction])

  const buildStrategy = useCallback((symbol: string, strategy: string) => {
    const { appendDelta, setError, onDone } = _startStreamingAction(
      i18n.t('commands.strategyMsg', { symbol, strategy })
    )
    streamStrategy(symbol, strategy, i18n.language, appendDelta, err => setError(classifyError(err)), onDone)
  }, [_startStreamingAction])

  const runPortfolioAnalysis = useCallback(() => {
    const { appendDelta, setError, onDone } = _startStreamingAction(
      i18n.t('commands.portfolioMsg')
    )
    streamPortfolioAnalysis(i18n.language, appendDelta, err => setError(classifyError(err)), onDone)
  }, [_startStreamingAction])

  return (
    <LLMContext.Provider value={{
      mode, provider, apiKey, setMode, setProvider, setApiKey, clearApiKey,
      getActivatedProviders, getApiKeyForProvider,
      byokActiveProvider, setByokActive, saveKeyForProvider,
      conversations, activeConversationId,
      messages: resolvedMessages,
      streaming,
      toolStatus,
      sendMessage, analyzeStock, newConversation, clearMessages,
      deleteConversation, switchConversation, resumeServerConversation, clearAllConversations, toggleFavorite, submitFeedback,
      providers, selectedModel, setSelectedModel: _setSelectedModel,
      selectedAgent, setSelectedAgent,
      chatOpen, openChat, closeChat, toggleChat,
      focusedSymbol, clearFocusedSymbol, analyzeFocusedStock,
      screenStocksAction, compareStocks, macroImpact, runCommittee, buildStrategy, runPortfolioAnalysis,
    }}>
      {children}
    </LLMContext.Provider>
  )
}

// Hook (useLLMContext) is in ./useLLMContext.ts to satisfy react-refresh/only-export-components
export { LLMContext }
