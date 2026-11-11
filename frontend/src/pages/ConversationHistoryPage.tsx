import { useState, useMemo, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { type Conversation } from '../contexts/LLMContext'
import { useLLMContext } from '../contexts/useLLMContext'
import { api, type ServerConversationSummary, type ConversationSearchHit } from '../api/client'

// ── Date grouping ─────────────────────────────────────────────────────────────

function getDateGroup(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfYesterday = new Date(startOfToday.getTime() - 86400000)
  const startOfWeek = new Date(startOfToday.getTime() - 6 * 86400000)
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1)

  if (d >= startOfToday) return 'Today'
  if (d >= startOfYesterday) return 'Yesterday'
  if (d >= startOfWeek) return 'This Week'
  if (d >= startOfMonth) return 'This Month'
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'long' })
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

// ── Export helpers ────────────────────────────────────────────────────────────

function exportAsJSON(conv: Conversation) {
  const blob = new Blob([JSON.stringify(conv, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `nova-chat-${conv.id}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function exportAsText(conv: Conversation): string {
  return conv.messages.map(m =>
    `[${m.role === 'user' ? 'You' : 'NOVA'}] ${new Date(m.timestamp).toLocaleTimeString()}\n${m.content}`
  ).join('\n\n---\n\n')
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).catch(() => {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  })
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StarIcon({ filled }: { filled: boolean }) {
  return filled ? (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="var(--color-accent)" stroke="var(--color-accent)" strokeWidth="1.5">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
    </svg>
  ) : (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
    </svg>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ConversationHistoryPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { conversations, activeConversationId, switchConversation, deleteConversation, toggleFavorite, clearAllConversations, openChat, resumeServerConversation } = useLLMContext()

  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<'all' | 'favorites' | 'cloud'>('all')
  const [selected, setSelected] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  // Cross-device (server) conversations. Loading is derived (null = not loaded yet)
  // to avoid a synchronous setState in the effect body.
  const [serverConvs, setServerConvs] = useState<ServerConversationSummary[] | null>(null)
  const [opening, setOpening] = useState<string | null>(null)
  const cloudLoading = filter === 'cloud' && serverConvs === null

  useEffect(() => {
    if (filter !== 'cloud') return
    let alive = true
    api.listConversations()
      .then(d => { if (alive) setServerConvs(d) })
      .catch(() => { if (alive) setServerConvs([]) })
    return () => { alive = false }
  }, [filter])

  // Recall: semantic search over your own past conversations (debounced).
  const [cloudResults, setCloudResults] = useState<ConversationSearchHit[] | null>(null)
  useEffect(() => {
    if (filter !== 'cloud') return
    const q = search.trim()
    let alive = true
    const id = setTimeout(() => {
      if (!q) { if (alive) setCloudResults(null); return }
      api.searchMyConversations(q)
        .then(r => { if (alive) setCloudResults(r) })
        .catch(() => { if (alive) setCloudResults([]) })
    }, 300)
    return () => { alive = false; clearTimeout(id) }
  }, [filter, search])

  const handleOpenServer = async (sid: string) => {
    setOpening(sid)
    const localId = await resumeServerConversation(sid)
    setOpening(null)
    if (localId) navigate('/')
  }

  const handleDeleteServer = async (sid: string) => {
    try { await api.deleteServerConversation(sid) } catch { /* noop */ }
    setServerConvs(prev => (prev ? prev.filter(c => c.id !== sid) : prev))
  }

  const filtered = useMemo(() => {
    let list = [...conversations].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    )
    if (filter === 'favorites') list = list.filter(c => c.isFavorite)
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(c =>
        (c.title || '').toLowerCase().includes(q) ||
        c.messages.some(m => m.content.toLowerCase().includes(q))
      )
    }
    return list
  }, [conversations, filter, search])

  // Group by date
  const groups = useMemo(() => {
    const map = new Map<string, Conversation[]>()
    for (const c of filtered) {
      const g = getDateGroup(c.createdAt)
      if (!map.has(g)) map.set(g, [])
      map.get(g)!.push(c)
    }
    return map
  }, [filtered])

  const selectedConv = selected ? conversations.find(c => c.id === selected) : null

  const handleOpen = (id: string) => {
    switchConversation(id)
    openChat()
    navigate('/')
  }

  const handleCopy = (conv: Conversation) => {
    copyToClipboard(exportAsText(conv))
    setCopiedId(conv.id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const handleDelete = (id: string) => {
    deleteConversation(id)
    if (selected === id) setSelected(null)
  }

  const handleClearAll = () => {
    if (!window.confirm(t('chat.historyConfirmClear'))) return
    clearAllConversations()
    setSelected(null)
  }

  return (
    <div className="flex flex-col gap-4">
      {/* ── Page header ────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-[var(--fd-text)] tracking-tight">{t('chat.historyTitle')}</h1>
          <p className="text-[11px] text-[var(--fd-text-dim)] mt-0.5">
            {conversations.length} {t('history.total')} · {conversations.filter(c => c.isFavorite).length} {t('history.favorites')}
          </p>
        </div>
        {conversations.length > 0 && (
          <button
            onClick={handleClearAll}
            className="text-[11px] text-[var(--fd-text-faint)] hover:text-[#ff6b6b] transition-colors px-2 py-1 border border-[var(--fd-rule)] hover:border-[#ff6b6b]"
          >
            {t('chat.historyDeleteAll')}
          </button>
        )}
      </div>

      {/* ── Search + filter ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2">
        <div className="flex-1 flex items-center gap-2 bg-[#0e1318] border border-[var(--fd-rule)] px-3 py-2">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#5a8aaa" strokeWidth="2" strokeLinecap="square">
            <circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder={t('history.searchPlaceholder')}
            className="flex-1 bg-transparent text-[var(--fd-text-secondary)] text-sm outline-none placeholder:text-[#4a7090]"
          />
          {search && (
            <button onClick={() => setSearch('')} className="text-[var(--fd-text-faint)] hover:text-[#888]">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          )}
        </div>
        <div className="flex">
          {(['all', 'favorites', 'cloud'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-2 text-[11px] font-semibold border transition-colors ${
                filter === f
                  ? 'bg-[var(--color-accent)] border-[var(--color-accent)] text-white'
                  : 'bg-[#0e1318] border-[var(--fd-rule)] text-[var(--fd-text-dim)] hover:text-[var(--fd-text-secondary)]'
              }`}
            >
              {f === 'all' ? t('history.filterAll') : f === 'favorites' ? t('history.filterFavorites') : t('history.filterCloud', '☁ Cloud')}
            </button>
          ))}
        </div>
      </div>

      {/* ── Cloud (cross-device) conversations ───────────────────────────────── */}
      {filter === 'cloud' ? (
        <div className="border border-[var(--fd-rule)]">
          <div className="px-3 py-2 border-b border-[var(--fd-rule)] text-[10px] text-[var(--fd-text-dim)]">
            {search.trim()
              ? t('history.recallHint', 'Searching your past conversations by meaning…')
              : t('history.cloudIntro', 'Conversations saved to your account — open on any device. Type above to search by meaning.')}
          </div>
          {search.trim() ? (
            cloudResults === null ? (
              <div className="text-center py-12 text-[11px] text-[var(--fd-text-faint)]">{t('common.loading', 'Loading…')}</div>
            ) : cloudResults.length === 0 ? (
              <div className="text-center py-12 text-[11px] text-[var(--fd-text-faint)]">{t('history.recallEmpty', 'No past conversations match that.')}</div>
            ) : (
              <div className="divide-y divide-[#0d1520]">
                {cloudResults.map(hit => (
                  <div key={hit.id} className="group flex items-center gap-3 px-3 py-2.5 bg-[#0a1018] hover:bg-[#0d1f35] transition-colors">
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] text-[#a8b8c8] leading-snug line-clamp-2">{hit.summary}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        {hit.when && <span className="text-[9px] text-[var(--fd-text-faint)]">{formatTime(hit.when)}</span>}
                        <span className="text-[8px] text-[var(--color-accent)]">{Math.round(hit.similarity * 100)}% {t('history.match', 'match')}</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleOpenServer(hit.id)}
                      disabled={opening === hit.id}
                      className="text-[10px] px-2 py-1 border border-[var(--fd-rule)] text-[var(--fd-text-dim)] hover:text-[var(--color-accent)] hover:border-[var(--color-accent)] transition-colors disabled:opacity-50"
                    >
                      {opening === hit.id ? t('common.loading', 'Loading…') : t('history.openInChat', 'Open')}
                    </button>
                  </div>
                ))}
              </div>
            )
          ) : cloudLoading ? (
            <div className="text-center py-12 text-[11px] text-[var(--fd-text-faint)]">{t('common.loading', 'Loading…')}</div>
          ) : !serverConvs || serverConvs.length === 0 ? (
            <div className="text-center py-12 text-[11px] text-[var(--fd-text-faint)]">{t('history.cloudEmpty', 'No saved conversations yet.')}</div>
          ) : (
            <div className="divide-y divide-[#0d1520]">
              {serverConvs.map(c => (
                <div key={c.id} className="group flex items-center gap-3 px-3 py-2.5 bg-[#0a1018] hover:bg-[#0d1f35] transition-colors">
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-semibold leading-tight truncate text-[var(--color-nova)]">{c.title || t('chat.newChat')}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[9px] text-[var(--fd-text-faint)]">{formatTime(c.updated_at)}</span>
                      <span className="text-[9px] text-[#2a4060]">·</span>
                      <span className="text-[9px] text-[var(--fd-text-faint)]">{c.message_count} {t('chat.historyMsgs')}</span>
                      {c.agent && <span className="text-[8px] bg-[#0d1f35] text-[var(--fd-text-dim)] px-1 py-px">{c.agent}</span>}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleOpenServer(c.id)}
                    disabled={opening === c.id}
                    className="text-[10px] px-2 py-1 border border-[var(--fd-rule)] text-[var(--fd-text-dim)] hover:text-[var(--color-accent)] hover:border-[var(--color-accent)] transition-colors disabled:opacity-50"
                  >
                    {opening === c.id ? t('common.loading', 'Loading…') : t('history.openInChat', 'Open')}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteServer(c.id)}
                    title={t('history.delete')}
                    className="p-1 text-[var(--fd-text-faint)] hover:text-[#ff6b6b] transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
                      <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-[var(--fd-text-faint)] text-sm">
          {search ? t('history.noResults') : t('chat.historyEmpty')}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.4fr] gap-4 items-start">

          {/* ── Conversation list ─────────────────────────────────────────── */}
          <div className="space-y-4">
            {Array.from(groups.entries()).map(([group, convs]) => (
              <div key={group}>
                <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--fd-text-faint)] mb-1.5 px-1">{group}</p>
                <div className="border border-[var(--fd-rule)] divide-y divide-[#0d1520]">
                  {convs.map(conv => {
                    const isActive = conv.id === activeConversationId
                    const isSelected = conv.id === selected
                    return (
                      <div
                        key={conv.id}
                        onClick={() => setSelected(conv.id)}
                        className={`group flex items-start gap-3 px-3 py-2.5 cursor-pointer transition-colors ${
                          isSelected ? 'bg-[var(--fd-bg-input-focus)]' : isActive ? 'bg-[#0a1a2e]' : 'bg-[#0a1018] hover:bg-[#0d1f35]'
                        }`}
                      >
                        {/* Favorite star */}
                        <button
                          type="button"
                          onClick={e => { e.stopPropagation(); toggleFavorite(conv.id) }}
                          className={`mt-0.5 shrink-0 transition-colors ${conv.isFavorite ? 'text-[var(--color-accent)]' : 'text-[#2a4060] hover:text-[var(--color-accent)]'}`}
                        >
                          <StarIcon filled={!!conv.isFavorite} />
                        </button>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <p className={`text-[11px] font-semibold leading-tight truncate ${isSelected ? 'text-[var(--fd-text)]' : 'text-[var(--color-nova)]'}`}>
                            {conv.title || t('chat.newChat')}
                          </p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[9px] text-[var(--fd-text-faint)]">{formatTime(conv.createdAt)}</span>
                            <span className="text-[9px] text-[#2a4060]">·</span>
                            <span className="text-[9px] text-[var(--fd-text-faint)]">{conv.messages.length} {t('chat.historyMsgs')}</span>
                            {isActive && (
                              <span className="text-[8px] bg-[var(--color-accent)]/20 text-[var(--color-accent)] px-1 py-px">{t('history.active')}</span>
                            )}
                          </div>
                        </div>

                        {/* Actions (shown on hover) */}
                        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                          <button
                            type="button"
                            onClick={e => { e.stopPropagation(); handleCopy(conv) }}
                            title={t('history.copy')}
                            className="p-1 text-[var(--fd-text-faint)] hover:text-[var(--color-nova)] transition-colors"
                          >
                            {copiedId === conv.id
                              ? <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="square"><polyline points="20 6 9 17 4 12"/></svg>
                              : <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square"><rect x="9" y="9" width="13" height="13"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                            }
                          </button>
                          <button
                            type="button"
                            onClick={e => { e.stopPropagation(); exportAsJSON(conv) }}
                            title={t('history.export')}
                            className="p-1 text-[var(--fd-text-faint)] hover:text-[var(--color-nova)] transition-colors"
                          >
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
                              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                          </button>
                          <button
                            type="button"
                            onClick={e => { e.stopPropagation(); handleDelete(conv.id) }}
                            title={t('history.delete')}
                            className="p-1 text-[var(--fd-text-faint)] hover:text-[#ff6b6b] transition-colors"
                          >
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
                              <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
                            </svg>
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* ── Detail panel ──────────────────────────────────────────────── */}
          <div className="border border-[var(--fd-rule)] bg-[#080f18] sticky top-20">
            {!selectedConv ? (
              <div className="flex items-center justify-center h-48 text-[11px] text-[var(--fd-text-faint)]">
                {t('history.selectToPreview')}
              </div>
            ) : (
              <>
                {/* Detail header */}
                <div className="flex items-start justify-between px-4 py-3 border-b border-[var(--fd-rule)]">
                  <div className="min-w-0 flex-1 mr-3">
                    <p className="text-sm font-semibold text-[var(--fd-text)] leading-tight">
                      {selectedConv.title || t('chat.newChat')}
                    </p>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span className="text-[10px] text-[var(--fd-text-dim)]">{formatTime(selectedConv.createdAt)}</span>
                      <span className="text-[10px] text-[var(--fd-text-faint)]">·</span>
                      <span className="text-[10px] text-[var(--fd-text-dim)]">{selectedConv.messages.length} {t('chat.historyMsgs')}</span>
                      <span className="text-[10px] text-[var(--fd-text-faint)]">·</span>
                      <span className="text-[9px] bg-[#0d1f35] text-[var(--fd-text-dim)] px-1.5 py-px uppercase tracking-wider">
                        {selectedConv.mode === 'flowdesktop' ? 'FlowDesktop AI' : selectedConv.provider?.toUpperCase() ?? 'BYOK'}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button onClick={() => toggleFavorite(selectedConv.id)} title={t('history.favorite')}
                      className={`p-1.5 transition-colors ${selectedConv.isFavorite ? 'text-[var(--color-accent)]' : 'text-[var(--fd-text-faint)] hover:text-[var(--color-accent)]'}`}>
                      <StarIcon filled={!!selectedConv.isFavorite} />
                    </button>
                    <button onClick={() => handleCopy(selectedConv)} title={t('history.copy')}
                      className="p-1.5 text-[var(--fd-text-faint)] hover:text-[var(--color-nova)] transition-colors">
                      {copiedId === selectedConv.id
                        ? <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="square"><polyline points="20 6 9 17 4 12"/></svg>
                        : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square"><rect x="9" y="9" width="13" height="13"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                      }
                    </button>
                    <button onClick={() => exportAsJSON(selectedConv)} title={t('history.export')}
                      className="p-1.5 text-[var(--fd-text-faint)] hover:text-[var(--color-nova)] transition-colors">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                      </svg>
                    </button>
                    <button onClick={() => handleOpen(selectedConv.id)} title={t('history.openInChat')}
                      className="p-1.5 text-[var(--fd-text-faint)] hover:text-[var(--color-accent)] transition-colors">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                      </svg>
                    </button>
                  </div>
                </div>

                {/* Message preview */}
                <div className="overflow-y-auto" style={{ maxHeight: 420 }}>
                  {selectedConv.messages.map(msg => (
                    <div key={msg.id} className={`px-4 py-2.5 border-b border-[#0a1018] ${msg.role === 'user' ? 'bg-[#0a1520]' : ''}`}>
                      <p className={`text-[9px] font-bold uppercase tracking-widest mb-1 ${msg.role === 'user' ? 'text-[var(--fd-text-dim)]' : 'text-[var(--color-nova)]'}`}>
                        {msg.role === 'user' ? t('chat.userPrefix') : 'NOVA'}
                      </p>
                      <p className="text-[11px] text-[#a8b8c8] leading-relaxed line-clamp-4 whitespace-pre-wrap">
                        {msg.content || '…'}
                      </p>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
