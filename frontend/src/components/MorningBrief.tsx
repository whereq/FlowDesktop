import { useState, useEffect, useCallback, startTransition } from 'react'
import ReactMarkdown from 'react-markdown'
import { useTranslation } from 'react-i18next'
import { streamMorningBrief } from '../api/client'
import { lsGet, lsSet } from '../utils/storage'
import { useAuth } from '../auth/useAuth'
import i18n from '../i18n'

const CACHE_KEY = 'FlowDesktop_morning_brief'
const CACHE_DATE_KEY = 'FlowDesktop_morning_brief_date'
const COLLAPSED_KEY = 'FlowDesktop_morning_brief_collapsed'

type State = 'idle' | 'loading' | 'streaming' | 'done' | 'error'

export default function MorningBrief() {
  const { t } = useTranslation()
  const { isAuthenticated } = useAuth()
  const [state, setState] = useState<State>('idle')
  const [content, setContent] = useState('')
  const [dismissed, setDismissed] = useState(false)
  // Collapsed by default if user already closed it; expanded on fresh load
  const [collapsed, setCollapsed] = useState(() => lsGet(COLLAPSED_KEY) === '1')

  const todayStr = new Date().toISOString().slice(0, 10)

  const generate = useCallback(() => {
    setState('loading')
    setContent('')
    setCollapsed(false)  // expand when regenerating

    streamMorningBrief(
      i18n.language,
      (delta) => {
        setState('streaming')
        setContent(prev => prev + delta)
      },
      () => {
        setState('error')
      },
      () => {
        setState(s => (s === 'streaming' ? 'done' : s))
      },
    )
  }, [])

  // Auto-generate once per day on first load
  useEffect(() => {
    if (!isAuthenticated) return
    const cachedDate = lsGet(CACHE_DATE_KEY)
    const cachedContent = lsGet(CACHE_KEY)

    if (cachedDate === todayStr && cachedContent && !cachedContent.includes('<think>')) {
      startTransition(() => {
        setContent(cachedContent)
        setState('done')
      })
      return
    }
    startTransition(() => generate())
  }, [isAuthenticated, todayStr, generate])

  // Persist to localStorage when done
  useEffect(() => {
    if (state === 'done' && content) {
      lsSet(CACHE_KEY, content)
      lsSet(CACHE_DATE_KEY, todayStr)
    }
  }, [state, content, todayStr])

  // Persist collapsed state
  useEffect(() => {
    lsSet(COLLAPSED_KEY, collapsed ? '1' : '0')
  }, [collapsed])

  if (!isAuthenticated || dismissed || state === 'error' || state === 'idle') return null

  const isLive = state === 'loading' || state === 'streaming'

  return (
    <div className="mb-3 border border-[var(--fd-rule)] bg-[var(--fd-bg)] overflow-hidden">
      {/* Collapsible header */}
      <div className="flex items-center h-8 border-b border-[var(--fd-rule)]">
        <button
          type="button"
          onClick={() => setCollapsed(c => !c)}
          className="flex-1 flex items-center gap-2 px-3 h-full text-left hover:bg-[#0d1520] transition-colors"
        >
          {/* Live pulse or chevron */}
          {isLive ? (
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent)] animate-pulse shrink-0" />
          ) : (
            <svg
              width="10" height="10" viewBox="0 0 24 24" fill="none"
              stroke="#3a5070" strokeWidth="2.5" strokeLinecap="square"
              className="shrink-0 transition-transform duration-150"
              style={{ transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}
            >
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          )}
          <span className="text-[var(--color-accent)] text-[10px] shrink-0">✦</span>
          <span className="text-[10px] font-semibold uppercase tracking-widest text-[#7ab0d8] truncate">
            {t('chat.morningBrief')}
          </span>
          <span className="text-[10px] text-[#5a8aaa] shrink-0">· {todayStr}</span>
        </button>

        {/* Actions */}
        <div className="flex items-center gap-px px-1 shrink-0">
          {state === 'done' && (
            <button
              onClick={generate}
              className="px-2 h-8 text-[10px] text-[#3a5070] hover:text-[var(--fd-text-secondary)] transition-colors"
              title="Refresh"
            >
              ↺
            </button>
          )}
          <button
            onClick={() => setDismissed(true)}
            className="px-2 h-8 text-[#3a5070] hover:text-[var(--fd-text-secondary)] transition-colors"
            title="Dismiss for this session"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Content — hidden when collapsed */}
      {!collapsed && (
        <div className="px-3 py-2.5">
          {state === 'loading' && (
            <div className="flex items-center gap-2 text-xs text-[#5a8aaa] py-1">
              <LoadingDots />
              <span>{t('chat.generatingBrief')}</span>
            </div>
          )}
          {(state === 'streaming' || state === 'done') && content && (
            <div className="markdown-body text-[#c8d8ea]">
              <ReactMarkdown>{content}</ReactMarkdown>
              {state === 'streaming' && (
                <span className="inline-block w-1 h-3.5 bg-[var(--color-accent)] animate-pulse ml-0.5 align-middle" />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function LoadingDots() {
  return (
    <span className="flex gap-1">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-1 h-1 rounded-full bg-[var(--color-accent)] animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </span>
  )
}
