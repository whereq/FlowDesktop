/**
 * NotificationCentre — bell icon with real-time in-app notification dropdown.
 *
 * Shows notifications from:
 *   alert_triggered  — user price/pct alerts that fired
 *   volume_spike     — abnormal trading volume for watchlisted stocks
 *   news_signal      — high-confidence LLM-extracted market signals
 *   sentiment_shift  — (reserved for future use)
 */
import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useNotificationSocket, type Notification } from '../hooks/useNotificationSocket'
import { useAuth } from '../auth/useAuth'
import { useLLMContext } from '../contexts/useLLMContext'
import { api } from '../api/client'

// ── Dot colors per notification type ─────────────────────────────────────────

const TYPE_DOT: Record<string, string> = {
  alert_triggered: 'bg-amber-400',
  volume_spike:    'bg-cyan-400',
  news_signal:     'bg-violet-400',
  sentiment_shift: 'bg-rose-400',
  agent_brief:     'bg-teal-400',
}

const TYPE_I18N_KEY: Record<string, string> = {
  alert_triggered: 'notif.typeAlert',
  volume_spike:    'notif.typeVolume',
  news_signal:     'notif.typeSignal',
  sentiment_shift: 'notif.typeShift',
  agent_brief:     'notif.typeBrief',
}

function NotifDot({ type }: { type: string }) {
  const dot = TYPE_DOT[type] ?? 'bg-gray-400'
  return <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dot}`} />
}

function TypeBadge({ type }: { type: string }) {
  const { t } = useTranslation()
  const key = TYPE_I18N_KEY[type]
  const label = key ? t(key) : type
  return (
    <span className="text-[9px] font-semibold uppercase tracking-wider text-[#5a8aaa]">
      {label}
    </span>
  )
}

function useTimeAgo(iso: string): string {
  const { t } = useTranslation()
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60_000)
  if (m < 1) return t('notif.justNow')
  if (m < 60) return t('notif.mAgo', { m })
  const h = Math.floor(m / 60)
  if (h < 24) return t('notif.hAgo', { h })
  return t('notif.dAgo', { d: Math.floor(h / 24) })
}

// ── Notification row ─────────────────────────────────────────────────────────

function NotifRow({
  notif,
  onRead,
  onAction,
}: {
  notif: Notification
  onRead: (id: number) => void
  onAction: () => void
}) {
  const { t } = useTranslation()
  const timeLabel = useTimeAgo(notif.created_at)
  const llm = useLLMContext()
  const [fb, setFb] = useState<1 | -1 | 0>(0)

  const md = notif.metadata ?? {}
  const isProactive = md.proactive === true
  const symbol = typeof md.symbol === 'string' ? md.symbol : null
  const signalType = typeof md.signal_type === 'string' ? md.signal_type : 'signal'

  const askNova = () => {
    if (!symbol) return
    llm.openChat()
    llm.sendMessage(`What's happening with ${symbol}? (${signalType})`)
    onRead(notif.id)
    onAction()
  }

  const rate = (rating: 1 | -1) => {
    if (fb !== 0) return
    setFb(rating)
    api.submitFeedback({
      rating,
      question: notif.title,
      answer: notif.body,
      agent: 'proactive',
    }).catch(() => { /* best-effort */ })
  }

  return (
    <div
      className={`flex items-start gap-3 px-4 py-2.5 border-b border-[#111] last:border-0 transition-colors ${
        notif.is_read ? 'opacity-60' : 'hover:bg-[var(--fd-bg-elev)]'
      }`}
    >
      <NotifDot type={notif.notification_type} />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <TypeBadge type={notif.notification_type} />
          {isProactive && (
            <span className="text-[8px] font-semibold uppercase tracking-wider text-[var(--color-nova)]">
              ✨ {t('notif.pulse')}
            </span>
          )}
          <span className="text-[9px] text-[#3a5060]">·</span>
          <span className="text-[9px] text-[#4a6070]">{timeLabel}</span>
        </div>
        <p className="text-[11px] font-semibold text-[#dde8f4] leading-tight">{notif.title}</p>
        {notif.body && (
          <p className="text-[10px] text-[#6a8aa8] mt-0.5 leading-snug line-clamp-2">{notif.body}</p>
        )}

        {isProactive && (
          <div className="flex items-center gap-2 mt-1.5">
            {symbol && (
              <button
                onClick={askNova}
                className="text-[9px] font-semibold px-1.5 py-0.5 border border-[var(--color-nova)]/40 text-[var(--color-nova)] hover:bg-[var(--color-nova)]/10 transition-colors"
              >
                {t('notif.askNova')}
              </button>
            )}
            <div className="flex items-center gap-1 ml-auto">
              <button
                onClick={() => rate(1)}
                disabled={fb !== 0}
                title={t('notif.helpful')}
                className={`text-[11px] leading-none p-0.5 transition-colors ${
                  fb === 1 ? 'text-green-400' : 'text-[#3a5060] hover:text-green-400'
                } disabled:cursor-default`}
              >
                👍
              </button>
              <button
                onClick={() => rate(-1)}
                disabled={fb !== 0}
                title={t('notif.notHelpful')}
                className={`text-[11px] leading-none p-0.5 transition-colors ${
                  fb === -1 ? 'text-rose-400' : 'text-[#3a5060] hover:text-rose-400'
                } disabled:cursor-default`}
              >
                👎
              </button>
            </div>
          </div>
        )}
      </div>

      {!notif.is_read && (
        <button
          onClick={() => onRead(notif.id)}
          title={t('notif.markRead')}
          className="flex-shrink-0 mt-0.5 p-0.5 text-[#3a5060] hover:text-[#7ab0d8] transition-colors"
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </button>
      )}
    </div>
  )
}

// ── Bell icon ─────────────────────────────────────────────────────────────────

function BellIcon({ hasUnread, isConnected }: { hasUnread: boolean; isConnected: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="square">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
      <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
      {hasUnread && isConnected && (
        <circle cx="19" cy="5" r="2.5" fill="var(--color-nova)" stroke="none" />
      )}
    </svg>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function NotificationCentre() {
  const { t } = useTranslation()
  const { isAuthenticated } = useAuth()
  const { notifications, unreadCount, markRead, markAllRead, isConnected } =
    useNotificationSocket(isAuthenticated)

  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  if (!isAuthenticated) return null

  const hasUnread = unreadCount > 0

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title={t('notif.title')}
        className={`relative flex items-center justify-center w-8 h-8 border transition-colors ${
          open
            ? 'border-[var(--color-accent)] bg-[var(--fd-bg-elev)] text-[var(--color-accent)]'
            : hasUnread
              ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20'
              : 'border-[var(--fd-rule-strong)] bg-[var(--fd-bg-panel)] text-[#8ab4d8] hover:text-[#a8d0f0] hover:bg-[var(--fd-bg-elev)]'
        }`}
      >
        <BellIcon hasUnread={hasUnread} isConnected={isConnected} />
        {hasUnread && (
          <span className="absolute -top-1 -right-1 min-w-[14px] h-[14px] bg-cyan-400 text-[#0d0d0d] text-[9px] font-bold rounded-full flex items-center justify-center px-0.5 leading-none">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-80 bg-[var(--fd-bg-panel)] border border-[var(--fd-rule-strong)] shadow-2xl z-50">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--fd-rule)]">
            <div className="flex items-center gap-2">
              <p className="text-[11px] font-semibold text-[#c8d8ea] tracking-widest uppercase">
                {t('notif.title')}
              </p>
              <span
                className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-400' : 'bg-[#3a5060]'}`}
                title={isConnected ? t('notif.live') : t('notif.reconnecting')}
              />
            </div>
            {hasUnread && (
              <button
                onClick={markAllRead}
                className="text-[10px] text-[#4a7090] hover:text-[#7ab0d8] transition-colors"
              >
                {t('notif.markAllRead')}
              </button>
            )}
          </div>

          {/* List */}
          {notifications.length === 0 ? (
            <p className="text-[var(--fd-text-faint)] text-xs px-4 py-6 text-center">{t('notif.empty')}</p>
          ) : (
            <div className="max-h-80 overflow-auto">
              {notifications.map((n) => (
                <NotifRow key={n.id} notif={n} onRead={markRead} onAction={() => setOpen(false)} />
              ))}
            </div>
          )}

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="border-t border-[var(--fd-rule)] px-4 py-2">
              <p className="text-[var(--fd-text-faint)] text-[10px]">
                {t('notif.count', { n: notifications.length })}
                {hasUnread && ' ' + t('notif.unread', { n: unreadCount })}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
