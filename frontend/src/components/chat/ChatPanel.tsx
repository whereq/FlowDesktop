import { startTransition, useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useParams } from 'react-router-dom'
import { useLLMContext } from '../../contexts/useLLMContext'
import { api, type ChatQuotaInfo } from '../../api/client'
import { lsSet, lsGet } from '../../utils/storage'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import CommandPalette from './CommandPalette'
import { CommandIcon } from './CommandIcon'
import { COMMANDS } from './commands'
import MorningBrief from '../MorningBrief'
import ShadowPortfolio from '../ShadowPortfolio'
import ConversationHistory from './ConversationHistory'
import novaUrl from '../../assets/nova.png'

const MIN_WIDTH = 300
const MAX_WIDTH = 800
const DEFAULT_WIDTH = 380
const APP_HEADER_HEIGHT = 56
const APP_FOOTER_HEIGHT = 50

interface ChatPanelProps {
  onClose: () => void
}

// ── Focused-strip icon button ─────────────────────────────────────────────────

function FocusedAction({
  id, title, onClick, disabled,
}: {
  id: string; title: string; onClick: () => void; disabled?: boolean
}) {
  return (
    <button
      type="button" onClick={onClick} disabled={disabled} title={title}
      className="flex items-center justify-center w-7 h-7 text-[#3a5070] hover:text-[var(--color-accent)] hover:bg-[var(--fd-bg-elev)] border border-transparent hover:border-[var(--fd-rule-strong)] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
    >
      <CommandIcon id={id} size={13} />
    </button>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ChatPanel({ onClose }: ChatPanelProps) {
  const { t } = useTranslation()
  const params = useParams()
  const {
    mode, messages, streaming, toolStatus,
    sendMessage, analyzeStock, runCommittee,
    newConversation, switchConversation, activeConversationId,
    focusedSymbol, clearFocusedSymbol,
    provider, apiKey, providers, selectedModel,
    selectedAgent, setSelectedAgent,
  } = useLLMContext()

  // Human-readable agent title from its slug (research_analyst → Research Analyst)
  const agentTitle = selectedAgent
    ? selectedAgent.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
    : null

  // Ensure there is always an active conversation so messages are persisted to history
  useEffect(() => {
    if (!activeConversationId) newConversation()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const [historyOpen, setHistoryOpen] = useState(false)
  const [portfolioVisible, setPortfolioVisible] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [paletteInitialCommand, setPaletteInitialCommand] = useState<string | undefined>()
  // Tracks which pill triggered the current AI response — stays lit while streaming
  const [activeCommandId, setActiveCommandId] = useState<string | undefined>()

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'ok' | 'fail'>('idle')

  const [panelWidth, setPanelWidth] = useState(() => {
    const saved = lsGet('FlowDesktop_chat_width')
    return saved ? Math.min(Math.max(parseInt(saved, 10), MIN_WIDTH), MAX_WIDTH) : DEFAULT_WIDTH
  })
  const panelWidthRef = useRef(panelWidth)
  const resizeHandleRef = useRef<HTMLDivElement>(null)
  const [quota, setQuota] = useState<ChatQuotaInfo | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const isBYOK = mode === 'byok'
  const isQuotaExhausted = mode === 'flowdesktop' && quota?.trial_exhausted === true
  const isDisabled = streaming || !!isQuotaExhausted

  const fetchQuota = useCallback(async () => {
    if (mode !== 'flowdesktop') return
    try { setQuota(await api.getChatQuota()) } catch { /* noop */ }
  }, [mode])
  useEffect(() => { const run = async () => { await fetchQuota() }; void run() }, [fetchQuota])
  useEffect(() => { const run = async () => { if (!streaming) await fetchQuota() }; void run() }, [streaming, fetchQuota])

  const openPalette = useCallback((initialCommand?: string) => {
    setPaletteInitialCommand(initialCommand)
    setPaletteOpen(true)
  }, [])

  const closePalette = useCallback(() => {
    setPaletteOpen(false)
    setPaletteInitialCommand(undefined)
  }, [])

  // Clear the active pill highlight once streaming finishes
  useEffect(() => {
    if (!streaming) startTransition(() => setActiveCommandId(undefined))
  }, [streaming])

  const handleTestConnection = async () => {
    if (!provider || !apiKey) return
    setTestStatus('testing')
    try {
      const res = await api.getChatProviders()
      setTestStatus(res && Array.isArray(res) ? 'ok' : 'fail')
    } catch { setTestStatus('fail') }
    setTimeout(() => setTestStatus('idle'), 3000)
  }

  useEffect(() => { panelWidthRef.current = panelWidth }, [panelWidth])

  useEffect(() => {
    const handle = resizeHandleRef.current
    if (!handle) return
    const onMouseDown = (e: MouseEvent) => {
      e.preventDefault()
      const startX = e.clientX
      const startW = panelWidthRef.current
      const onMove = (ev: MouseEvent) => {
        setPanelWidth(Math.min(Math.max(startW + (startX - ev.clientX), MIN_WIDTH), MAX_WIDTH))
      }
      const onUp = (ev: MouseEvent) => {
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
        document.body.style.cursor = ''
        document.body.style.userSelect = ''
        lsSet('FlowDesktop_chat_width', String(Math.min(Math.max(startW + (startX - ev.clientX), MIN_WIDTH), MAX_WIDTH)))
      }
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
    }
    handle.addEventListener('mousedown', onMouseDown)
    return () => handle.removeEventListener('mousedown', onMouseDown)
  }, [])

  const headerLabel = (() => {
    if (mode === 'flowdesktop') return t('chat.modePlatform')
    if (!provider) return t('chat.notConfigured')
    const meta = providers.find(p => p.name === provider)
    const modelLabel = meta?.models.find(m => m.id === selectedModel)?.label ?? selectedModel
    return `${provider.toUpperCase()} / ${modelLabel}`
  })()

  const headerLabelColor = mode === 'flowdesktop' ? 'text-[var(--color-nova)]' : !provider ? 'text-red-400' : 'text-[var(--color-nova)]'

  const quotaBarColor = (() => {
    if (!quota || quota.tier === 'admin' || quota.limit === null) return null
    const pct = quota.used / quota.limit
    return pct >= 1 ? 'bg-red-600' : pct >= 0.7 ? 'bg-amber-500' : 'bg-[var(--color-accent)]'
  })()

  const quotaTextColor = (() => {
    if (!quota || quota.tier === 'admin' || quota.limit === null) return null
    const pct = quota.used / quota.limit
    return pct >= 1 ? 'text-red-400' : pct >= 0.7 ? 'text-amber-400' : 'text-[#aaa]'
  })()

  const quotaNumColor = (() => {
    if (!quota || quota.tier === 'admin' || quota.limit === null) return 'text-[#e0e0e0]'
    const pct = quota.used / quota.limit
    return pct >= 1 ? 'text-red-300' : pct >= 0.7 ? 'text-amber-300' : 'text-[#e0e0e0]'
  })()

  // Symbol context — URL param takes precedence, then focused symbol
  const contextSymbol = params.symbol || focusedSymbol || ''

  // Pill click — smart shortcut: fire immediately if possible, else open palette
  function handlePillClick(id: string) {
    if (isDisabled) return
    if (id === 'portfolio') { setPortfolioVisible(v => !v); return }
    const cmd = COMMANDS.find(c => c.id === id)
    if (!cmd) return
    // Analyze / committee with a known symbol → fire directly, mark pill active
    if (!cmd.needsInput && contextSymbol) {
      if (id === 'analyze') { setActiveCommandId(id); analyzeStock(contextSymbol); return }
      if (id === 'committee') { setActiveCommandId(id); runCommittee(contextSymbol); return }
    }
    // Everything else → open palette at that command
    openPalette(id)
  }

  return (
    <>
      {/* Mobile backdrop */}
      <div className="fixed inset-0 z-40 bg-black/40 md:hidden" onClick={onClose} />

      {/* Drawer */}
      <div
        className="fixed z-50 right-0 bg-[var(--fd-bg-panel)] border-l border-[var(--fd-rule)] flex flex-col"
        style={{
          top: APP_HEADER_HEIGHT,
          height: `calc(100vh - ${APP_HEADER_HEIGHT}px - ${APP_FOOTER_HEIGHT}px)`,
          width: panelWidth,
          maxWidth: '100vw',
          boxShadow: '-8px 0 32px rgba(0,0,0,0.6)',
        }}
      >
        {/* Resize handle */}
        <div ref={resizeHandleRef} className="absolute left-0 top-0 bottom-0 w-3 z-10 cursor-col-resize group">
          <div className="absolute left-0 top-0 bottom-0 w-px bg-[var(--fd-rule)] group-hover:bg-[var(--color-accent)] transition-colors" />
        </div>

        {/* ── Header — no settings icon (already in app header) ──────────── */}
        <div className="flex items-center justify-between pl-4 pr-2 h-11 border-b border-[var(--fd-rule)] shrink-0">
          <span className={`text-[11px] font-semibold uppercase tracking-widest truncate ${headerLabelColor}`}>
            {headerLabel}
          </span>
          <div className="flex items-center gap-0.5 shrink-0">
            {isBYOK && provider && (
              <button
                type="button" onClick={handleTestConnection}
                disabled={testStatus === 'testing' || !apiKey}
                className={`text-[10px] px-2 py-0.5 border transition-colors mr-1 ${
                  testStatus === 'ok' ? 'border-green-500 text-green-400'
                  : testStatus === 'fail' ? 'border-red-500 text-red-400'
                  : testStatus === 'testing' ? 'border-yellow-500 text-yellow-400'
                  : 'border-[var(--fd-text-faint)] text-[var(--fd-text-dim)] hover:border-[#666] hover:text-[#aaa]'
                }`}
                title={t('chat.testConnection')}
              >
                {testStatus === 'testing' ? '...' : testStatus === 'ok' ? '✓' : testStatus === 'fail' ? '✗' : t('chat.testConnection')}
              </button>
            )}
            {/* History */}
            <button
              type="button"
              onClick={() => setHistoryOpen(o => !o)}
              className={`p-1.5 transition-colors ${historyOpen ? 'text-[var(--color-accent)]' : 'text-[var(--fd-text-dim)] hover:text-[#f0f0f0]'}`}
              title={t('chat.historyTitle')}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                <polyline points="9 22 9 12 15 12 15 22"/>
              </svg>
            </button>
            {/* Close only — settings is in the main app header */}
            <button type="button" onClick={onClose} className="p-1.5 text-[var(--fd-text-dim)] hover:text-[#f0f0f0] transition-colors" title={t('chat.close')}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        {/* ── Quota bar ───────────────────────────────────────────────────── */}
        {mode === 'flowdesktop' && quota && quota.tier === 'free' && quota.limit !== null && (
          <div className="shrink-0 border-b border-[var(--fd-rule)]">
            <div className="h-0.5 w-full bg-[#111]">
              <div className={`h-full transition-all duration-300 ${quotaBarColor}`}
                style={{ width: `${Math.min(100, (quota.used / quota.limit) * 100)}%` }} />
            </div>
            <div className="flex items-center justify-between px-4 py-1">
              <span className={`text-[10px] ${quotaTextColor}`}>
                <span className={`font-semibold ${quotaNumColor}`}>{quota.used}</span>
                {' / '}
                <span className={`font-semibold ${quotaNumColor}`}>{quota.limit}</span>
                {' '}{t('chat.quotaUsageSuffix')}
              </span>
              {quota.days_remaining !== null && !quota.trial_exhausted && (
                <span className="text-[10px] text-[var(--fd-text-dim)]">
                  <span className="font-semibold text-[var(--fd-text-secondary)]">{quota.days_remaining}</span>
                  {' '}{t('chat.quotaResetsInSuffix')}
                </span>
              )}
            </div>
          </div>
        )}

        {/* ── Focused symbol strip ─────────────────────────────────────────
            Only visible when a stock row has been clicked in the table.
            Shows 4 icon action buttons: analyze, committee, compare, strategy. */}
        {focusedSymbol && (
          <div className="shrink-0 flex items-center justify-between px-3 h-9 bg-[var(--fd-bg-panel)] border-b border-[var(--fd-rule)]">
            <div className="flex items-center gap-2 min-w-0">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 3L13.5 8.5L19 10L13.5 11.5L12 17L10.5 11.5L5 10L10.5 8.5Z"/>
              </svg>
              <span className="text-[11px] font-semibold font-mono text-[var(--color-accent)] uppercase tracking-widest">{focusedSymbol}</span>
            </div>
            <div className="flex items-center gap-0.5">
              <FocusedAction id="analyze"   title="Analyze"             onClick={() => !streaming && analyzeStock(focusedSymbol)} disabled={streaming} />
              <FocusedAction id="committee" title="Investment Committee" onClick={() => !streaming && runCommittee(focusedSymbol)} disabled={streaming} />
              <FocusedAction id="compare"   title="Compare with..."     onClick={() => openPalette('compare')} />
              <FocusedAction id="strategy"  title="Strategy Builder"    onClick={() => openPalette('strategy')} />
              <div className="w-px h-4 bg-[var(--fd-rule)] mx-1" />
              <button onClick={clearFocusedSymbol} title="Clear focus"
                className="flex items-center justify-center w-7 h-7 text-[#2a4060] hover:text-[#6a90b0] transition-colors">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* ── Action pills — horizontal scroll, always visible ─────────────
            Physical buttons for discoverability. Clicking:
            • analyze / committee + focused symbol → fires immediately
            • anything else → opens command palette at that command
            Commands that need a symbol but none is focused will prompt
            for the symbol as the first step inside the palette.           */}
        {!isQuotaExhausted && (
          <div className="shrink-0 flex items-center gap-1.5 px-3 py-2 overflow-x-auto border-b border-[var(--fd-rule)]"
            style={{ scrollbarWidth: 'none' }}>
            {COMMANDS.map(cmd => (
              <button
                key={cmd.id}
                type="button"
                onClick={() => handlePillClick(cmd.id)}
                disabled={isDisabled}
                title={cmd.description}
                style={activeCommandId === cmd.id ? { opacity: 1 } : undefined}
                className={`shrink-0 flex items-center gap-1.5 px-2.5 py-1 border transition-colors text-[11px] font-medium disabled:opacity-30 disabled:cursor-not-allowed ${
                  (paletteOpen && paletteInitialCommand === cmd.id) || activeCommandId === cmd.id
                    ? 'border-[var(--color-accent)] bg-[var(--fd-bg-elev)] text-[#e0ecf8]'
                    : 'border-[var(--fd-rule)] bg-[var(--fd-bg)] hover:border-[var(--color-accent)] hover:bg-[var(--fd-bg-elev)] text-[#8ab8d8] hover:text-[#e0ecf8]'
                }`}
              >
                <span className="text-[var(--color-accent)]"><CommandIcon id={cmd.id} size={12} /></span>
                {t(`commands.${cmd.id}.short`)}
              </button>
            ))}
          </div>
        )}

        {/* ── History panel ────────────────────────────────────────────────── */}
        {historyOpen && (
          <div className="flex-1 overflow-hidden">
            <ConversationHistory
              onClose={() => setHistoryOpen(false)}
              onSelect={(id) => { switchConversation(id); setHistoryOpen(false) }}
              onNew={() => { newConversation(); setHistoryOpen(false) }}
            />
          </div>
        )}

        {/* ── Active agent strip ───────────────────────────────────────────── */}
        {agentTitle && !historyOpen && (
          <div className="shrink-0 flex items-center gap-2 px-3 py-1.5 border-b border-[var(--fd-rule)] bg-[var(--fd-bg-elev)]">
            <span style={{ fontSize: 11, color: 'var(--color-nova)', fontWeight: 600 }}>🤖 {agentTitle}</span>
            <span style={{ fontSize: 10, color: 'var(--fd-text-faint)' }}>{t('chat.agentActive', 'agent mode')}</span>
            <button
              type="button"
              onClick={() => setSelectedAgent(null)}
              title={t('chat.agentClear', 'Exit agent mode')}
              className="ml-auto text-[10px] px-1.5 py-0.5 border border-[var(--fd-rule)] text-[var(--fd-text-dim)] hover:text-[var(--fd-text-primary)]"
              style={{ borderRadius: 2 }}
            >
              {t('chat.agentExit', 'General')} ✕
            </button>
          </div>
        )}

        {/* ── Messages area ────────────────────────────────────────────────── */}
        <div className={`flex-1 overflow-y-auto thin-scrollbar-ai ${historyOpen ? 'hidden' : ''}`}>
          <div className="px-3 py-3 space-y-3">

            {/* Morning Brief — collapsible; platform mode only.
                Auto-generates once per day from the user's watchlist stocks + FRED
                macro indicators. Gives a pre-market summary without typing anything. */}
            {mode === 'flowdesktop' && <MorningBrief />}

            {/* Shadow Portfolio */}
            {portfolioVisible && (
              <div className="border border-[var(--fd-rule)] mb-1">
                <ShadowPortfolio />
              </div>
            )}

            {messages.map(msg => <ChatMessage key={msg.id} message={msg} />)}

            {/* Streaming indicator */}
            {streaming && (
              <div style={{ display: 'flex', justifyContent: 'flex-start', alignItems: 'flex-start', gap: 6 }}>
                <img
                  src={novaUrl}
                  alt="NOVA"
                  style={{ width: 26, height: 26, minWidth: 26, borderRadius: '50%', objectFit: 'cover', flexShrink: 0, marginTop: 2 }}
                />
                <div className="bg-[var(--fd-bg-elev)] border border-[var(--fd-rule-strong)] px-3 py-2 max-w-[80%] min-w-35">
                  <p className="text-[9px] font-bold uppercase tracking-wider text-[var(--color-nova)] mb-1.5">{t('chat.aiPrefix')}</p>
                  {toolStatus === 'fetching_data' ? (
                    <div>
                      <p className="text-[10px] text-[#5a8aaa] mb-1.5">{t('chat.fetchingData')}</p>
                      <div className="h-0.5 w-full bg-[#111] overflow-hidden">
                        <div className="h-full bg-[var(--color-accent)] animate-progress-indeterminate" />
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1">
                      {[0, 1, 2].map(i => (
                        <span key={i} className="w-1.5 h-1.5 bg-[var(--color-accent)] rounded-full animate-bounce"
                          style={{ animationDelay: `${i * 150}ms` }} />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Trial exhausted */}
            {isQuotaExhausted && (
              <div className="p-3 bg-[#1a0800] border border-[#7c3800]">
                <p className="text-xs font-semibold text-amber-400">{t('chat.quotaExhausted')}</p>
                <p className="text-[10px] text-[#666] mt-0.5">
                  {quota?.exhausted_reason === 'time'
                    ? t('chat.quotaResetsIn', { days: 0 })
                    : t('chat.quotaUsage', { used: quota?.used ?? 0, limit: quota?.limit ?? 0 })}
                </p>
                <Link to="/pricing" onClick={onClose} className="inline-block text-[10px] text-[var(--color-accent)] hover:text-[var(--color-nova)] mt-1 transition-colors">
                  {t('chat.quotaUpgradeHint')} →
                </Link>
              </div>
            )}

            {/* Empty state */}
            {messages.length === 0 && !streaming && !isQuotaExhausted && (
              <div className="flex flex-col items-center justify-center py-6 gap-2">
                <p className="text-[11px] text-[#5a8aaa] text-center leading-relaxed">
                  {contextSymbol
                    ? <>Analyzing <span className="text-[var(--color-accent)] font-mono">{contextSymbol}</span>?<br/>Use the buttons above, or type a question below.</>
                    : <>Use the buttons above, or press <span className="text-[var(--color-accent)] font-mono">/</span> for all commands.<br/>Click <span className="text-[var(--color-accent)]">✦</span> on a stock row to focus a symbol.</>
                  }
                </p>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* ── Command palette + input (hidden when history open) ───────────── */}
        {!historyOpen && (
          <>
            {paletteOpen && (
              <CommandPalette
                initialCommand={paletteInitialCommand}
                disabled={isDisabled}
                onClose={closePalette}
                onPortfolioToggle={() => { setPortfolioVisible(v => !v); closePalette() }}
                onExecute={(id) => setActiveCommandId(id)}
              />
            )}
            <ChatInput
              onSend={sendMessage}
              onPaletteOpen={() => openPalette()}
              disabled={isDisabled}
            />
            <p className="px-3 pb-1.5 pt-0.5 text-[9px] leading-tight text-center text-[#3a6080]">
              {t('chat.disclaimer', 'NOVA can be wrong and may use delayed data. Research & education, not financial advice.')}
            </p>
          </>
        )}
      </div>
    </>
  )
}
