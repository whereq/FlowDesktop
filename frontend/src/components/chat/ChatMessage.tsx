import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FaTrafficLight } from 'react-icons/fa6'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage as ChatMessageType } from '../../contexts/LLMContext'
import { api, addShadowTrade, type ActionProposal } from '../../api/client'
import { useAuth } from '../../auth/useAuth'
import { useAvatar } from '../../contexts/useAvatarContext'
import { useLLMContext } from '../../contexts/useLLMContext'
import novaUrl from '../../assets/nova.png'
import UserAvatar from '../icons/UserAvatar'
import ChatChart from './ChatChart'

interface ChatMessageProps {
  message: ChatMessageType
}

/** Friendly labels for the data tools NOVA used (citations row). */
const TOOL_LABELS: Record<string, string> = {
  get_stock_quote: 'Quote', fetch_live_quote: 'Live quote', get_price_history: 'Price history',
  get_technical_indicators: 'Technicals', get_fundamentals: 'Fundamentals',
  get_news_and_signals: 'News & signals', get_sector_summary: 'Sector', get_sector_intelligence: 'Sector intel',
  get_peers_and_correlations: 'Peers', get_macro_indicators: 'Macro', get_market_movers: 'Movers',
  compare_stocks: 'Comparison', search_stocks: 'Search', get_watchlist: 'Watchlist',
  get_portfolio: 'Portfolio', get_user_alerts: 'Alerts', web_fetch: 'Web page', web_search: 'Web search',
  save_memory: 'Memory', semantic_news_search: 'News (semantic)',
  search_my_conversations: 'Your history', get_calendar_events: 'Calendar', run_backtest: 'Backtest',
  search_filings: 'SEC filings', get_insider_activity: 'Insider (Form 4)',
  get_short_interest: 'Short interest', get_congress_trades: 'Congress trades',
  get_sim_portfolio: 'Sim portfolio', run_sim_backtest: 'Sim backtest',
}

/** Compact "as of" formatter for provenance chips. Date-only stays a date; a
 *  full timestamp shows month/day + HH:MM. Falls back to the raw string. */
function fmtAsOf(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const hasTime = /[T ]\d{2}:\d{2}/.test(iso)
  return hasTime
    ? d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

/** Confirmation card for a NOVA-proposed write action (alert / watchlist / trade). */
function ActionCard({ proposal }: { proposal: ActionProposal }) {
  const { t } = useTranslation()
  const [state, setState] = useState<'idle' | 'working' | 'done' | 'error'>('idle')
  const [errMsg, setErrMsg] = useState('')

  const confirm = async () => {
    setState('working')
    try {
      const a = proposal.args
      if (proposal.action === 'create_alert') {
        await api.createAlert(String(a.symbol), a.alert_type as never, Number(a.threshold))
      } else if (proposal.action === 'add_to_watchlist') {
        await api.addToWatchlist(String(a.symbol))
      } else if (proposal.action === 'record_trade') {
        await addShadowTrade({
          symbol: String(a.symbol), action: String(a.action),
          shares: Number(a.shares), price: Number(a.price),
          note: (a.note as string) ?? null,
        })
      } else if (proposal.action === 'sim_order') {
        // Mirror OrderTicket.tsx: place via the existing /me/sim/* endpoint with a
        // fresh idempotency key so a double-click of Confirm can't double-fill.
        await api.placeSimOrder(Number(a.account_id), {
          symbol: String(a.symbol),
          side: String(a.side) as 'buy' | 'sell',
          order_type: String(a.order_type) as 'market' | 'limit',
          quantity: Number(a.quantity),
          limit_price: a.limit_price == null ? null : Number(a.limit_price),
          idempotency_key: crypto.randomUUID(),
        })
      }
      setState('done')
    } catch (e) {
      setErrMsg(e instanceof Error ? e.message : 'Failed')
      setState('error')
    }
  }

  return (
    <div className="mt-2 border border-[var(--color-nova)] bg-[#0a1929] px-3 py-2">
      <p className="text-[11px] text-[#9fb8d4] mb-2">{proposal.label}</p>
      {state === 'done' ? (
        <p className="text-[11px] text-[#4ea86d] font-medium">✓ {t('chat.actionDone', 'Done')}</p>
      ) : state === 'error' ? (
        <p className="text-[11px] text-[#c8a84a]">{t('chat.actionFailed', 'Could not complete')}: {errMsg}</p>
      ) : (
        <div className="flex items-center gap-2">
          <button
            type="button" disabled={state === 'working'} onClick={confirm}
            className="px-3 py-1 text-[11px] font-semibold bg-[var(--color-nova)] text-[#06121f] disabled:opacity-50"
          >
            {state === 'working' ? t('chat.actionWorking', 'Working…') : t('chat.actionConfirm', 'Confirm')}
          </button>
          <button
            type="button" disabled={state === 'working'} onClick={() => setState('done')}
            className="px-3 py-1 text-[11px] text-[#6a90b0] hover:text-[#9fb8d4]"
          >
            {t('chat.actionDismiss', 'Dismiss')}
          </button>
        </div>
      )}
    </div>
  )
}

/** Strip all <think>…</think> blocks; collect their text for the collapsible. */
function parseThinking(content: string): { thinking: string; visible: string } {
  const parts: string[] = []
  let visible = content.replace(/<think>([\s\S]*?)<\/think>/gi, (_, inner) => {
    const trimmed = inner.trim()
    if (trimmed) parts.push(trimmed)
    return ''
  })
  const openIdx = visible.indexOf('<think>')
  if (openIdx !== -1) visible = visible.slice(0, openIdx)
  return { thinking: parts.join('\n\n---\n\n'), visible: visible.trim() }
}

const SZ = 26  // avatar diameter in px

export default function ChatMessage({ message }: ChatMessageProps) {
  const { t } = useTranslation()
  const { isAuthenticated } = useAuth()
  const { submitFeedback } = useLLMContext()
  const { effectiveUrl } = useAvatar()
  const avatar = isAuthenticated ? effectiveUrl : null
  const [thinkOpen, setThinkOpen] = useState(false)
  const isUser = message.role === 'user'
  const { thinking, visible } = parseThinking(message.content)
  const [shared, setShared] = useState(false)

  const doShare = async () => {
    try {
      const firstLine = visible.split('\n').find(l => l.trim()) || 'NOVA analysis'
      const title = firstLine.replace(/^#+\s*/, '').replace(/\*\*/g, '').slice(0, 120)
      const { path } = await api.createShare({ title, content: visible })
      const url = window.location.origin + path
      try { await navigator.clipboard.writeText(url) } catch { /* clipboard blocked */ }
      setShared(true)
      setTimeout(() => setShared(false), 4000)
    } catch { /* noop */ }
  }

  /** User avatar: real Keycloak picture → UserSignedInIcon → nothing for guest */
  const userAvatar = (
    <span style={{ width: SZ, height: SZ, minWidth: SZ, flexShrink: 0, marginTop: 2, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <UserAvatar avatar={avatar} isAuthenticated={isAuthenticated} size={SZ} />
    </span>
  )

  /** NOVA avatar: bundled nova PNG (Vite asset import — always resolves) */
  const novaAvatar = (
    <img
      src={novaUrl}
      alt="NOVA"
      style={{ width: SZ, height: SZ, minWidth: SZ, borderRadius: '50%', objectFit: 'cover', flexShrink: 0, marginTop: 2 }}
    />
  )

  if (isUser) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'flex-start', gap: 6 }}>
        <div className="max-w-[80%] bg-[#1a2e44] px-3 py-2">
          <div className="text-sm leading-relaxed markdown-body text-[#eef2f7]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{visible}</ReactMarkdown>
          </div>
        </div>
        {userAvatar}
      </div>
    )
  }

  // AI message
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-start', alignItems: 'flex-start', gap: 6 }}>
      {novaAvatar}
      <div
        className={`max-w-[80%] px-3 py-2 ${
          message.isError
            ? 'bg-[#1a1800] text-[#c8a84a]'
            : 'bg-[#0d1f35] text-[#dde8f4]'
        }`}
      >
        <p className="text-[9px] font-bold uppercase tracking-wider text-[var(--color-nova)] mb-1">
          {t('chat.aiPrefix')}
        </p>

        {thinking && (
          <div className="mb-2">
            <button
              type="button"
              onClick={() => setThinkOpen(o => !o)}
              className="flex items-center gap-1 text-[10px] text-[#3a6080] hover:text-[#6a9cc0] transition-colors"
            >
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                {thinkOpen
                  ? <polyline points="18 15 12 9 6 15" />
                  : <polyline points="6 9 12 15 18 9" />}
              </svg>
              {t('chat.reasoning', 'Reasoning')}
            </button>
            {thinkOpen && (
              <div className="mt-1 pl-2 border-l border-[#1e3a5a] text-[11px] text-[#4a7090] leading-relaxed whitespace-pre-wrap">
                {thinking}
              </div>
            )}
          </div>
        )}

        <div className="text-sm leading-relaxed markdown-body">
          {message.isError ? (
            <p className="flex items-start gap-1.5">
              <FaTrafficLight className="text-yellow-400 shrink-0 mt-0.5" size={13} />
              <span>{visible || t('chat.errorTransient')}</span>
            </p>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{visible}</ReactMarkdown>
          )}
        </div>

        {/* Auto-dispatched agent indicator (router picked a specialized agent) */}
        {!isUser && message.autoAgent && (
          <div className="mt-1.5">
            <span className="inline-flex items-center gap-1 text-[10px] text-[#9cc3e0] bg-[#0a1929] border border-[#1e3a5a] px-1.5 py-0.5">
              ✨ {t('chat.viaAgent', 'via')} {message.autoAgent.title}
            </span>
          </div>
        )}

        {/* Inline charts NOVA rendered */}
        {message.charts?.map((c, i) => <ChatChart key={i} spec={c} />)}

        {/* Gated action confirmation cards */}
        {message.actions?.map((p, i) => <ActionCard key={i} proposal={p} />)}

        {/* Citations: verifiable provenance (source + as-of) for the data NOVA used,
            falling back to the legacy tool-label chips when no provenance is present */}
        {message.sources && message.sources.length > 0 ? (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 pt-1.5 border-t border-[#1e3a5a]">
            <span className="text-[9px] uppercase tracking-wider text-[#3a6080]">
              {t('chat.sources', 'Sources')}
            </span>
            {message.sources.map((s, i) => (
              <span key={i} className="text-[10px] text-[#7fa3c4] bg-[#0a1929] border border-[#1e3a5a] px-1.5 py-0.5">
                {TOOL_LABELS[s.tool] ?? s.tool}
                {s.symbol ? ` ${s.symbol}` : ''}
                {s.source ? ` · ${s.source}` : ''}
                {s.as_of ? ` · ${t('chat.asOf', 'as of')} ${fmtAsOf(s.as_of)}` : ''}
              </span>
            ))}
          </div>
        ) : message.toolsUsed && message.toolsUsed.length > 0 ? (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 pt-1.5 border-t border-[#1e3a5a]">
            <span className="text-[9px] uppercase tracking-wider text-[#3a6080]">
              {t('chat.sources', 'Sources')}
            </span>
            {message.toolsUsed.map(tool => (
              <span key={tool} className="text-[10px] text-[#7fa3c4] bg-[#0a1929] border border-[#1e3a5a] px-1.5 py-0.5">
                {TOOL_LABELS[tool] ?? tool}
              </span>
            ))}
          </div>
        ) : null}

        {/* Feedback (👍/👎) + Share */}
        {!isUser && !message.isError && isAuthenticated && visible.trim().length > 40 && (
          <div className="mt-2 flex items-center gap-3">
            <button onClick={doShare}
              className="text-[10px] text-[#7fa3c4] hover:text-[var(--color-nova)]"
              title={t('chat.shareHint', 'Create a public link to this analysis')}>
              {shared ? `✓ ${t('chat.linkCopied', 'Link copied!')}` : `↗ ${t('chat.share', 'Share')}`}
            </button>
            <span className="flex items-center gap-1.5">
              <button
                onClick={() => submitFeedback(message.id, 1)}
                title={t('chat.feedbackUp', 'Helpful')}
                className={`text-[12px] transition-colors ${message.feedback === 1 ? 'text-[var(--color-accent)]' : 'text-[#3a6080] hover:text-[var(--color-nova)]'}`}
              >👍</button>
              <button
                onClick={() => submitFeedback(message.id, -1)}
                title={t('chat.feedbackDown', 'Not helpful')}
                className={`text-[12px] transition-colors ${message.feedback === -1 ? 'text-[#ff6b6b]' : 'text-[#3a6080] hover:text-[#ff6b6b]'}`}
              >👎</button>
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
