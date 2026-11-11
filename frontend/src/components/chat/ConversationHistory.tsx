import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useLLMContext } from '../../contexts/useLLMContext'

interface Props {
  onClose: () => void
  onSelect: (id: string) => void
  onNew: () => void
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffH = diffMs / 3600000
  if (diffH < 1) return '< 1h ago'
  if (diffH < 24) return `${Math.floor(diffH)}h ago`
  if (diffH < 48) return 'Yesterday'
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export default function ConversationHistory({ onClose, onSelect, onNew }: Props) {
  const { t } = useTranslation()
  const { conversations, activeConversationId, deleteConversation, newConversation, clearAllConversations } = useLLMContext()

  const sorted = [...conversations].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  )

  const handleNew = () => {
    newConversation()
    onNew()
  }

  const handleClearAll = () => {
    if (!window.confirm(t('chat.historyConfirmClear'))) return
    clearAllConversations()
    onNew()
  }

  return (
    <div className="flex flex-col h-full bg-[#080f18]">
      {/* Header */}
      <div className="flex items-center justify-between px-3 h-9 border-b border-[var(--fd-rule)] shrink-0">
        <span className="text-[10px] font-bold uppercase tracking-widest text-[#5a8aaa]">
          {t('chat.historyTitle')}
        </span>
        <button
          type="button"
          onClick={onClose}
          className="p-1 text-[#3a5070] hover:text-[var(--fd-text-secondary)] transition-colors"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="square">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      {/* Manage link */}
      <div className="px-3 py-1.5 shrink-0 border-b border-[var(--fd-rule)] flex justify-end">
        <Link to="/history" onClick={onClose} className="text-[9px] text-[#3a5070] hover:text-[#7ab0d8] transition-colors uppercase tracking-wider">
          {t('history.manage')} →
        </Link>
      </div>

      {/* New chat button */}
      <div className="px-3 py-2 shrink-0 border-b border-[var(--fd-rule)]">
        <button
          type="button"
          onClick={handleNew}
          className="w-full flex items-center gap-2 px-3 py-1.5 bg-[var(--color-accent)] hover:bg-[#106ebe] text-white text-[11px] font-semibold transition-colors"
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="square">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          {t('chat.newChat')}
        </button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 ? (
          <p className="text-[11px] text-[#3a5070] text-center mt-8">{t('chat.historyEmpty')}</p>
        ) : (
          sorted.map(conv => {
            const isActive = conv.id === activeConversationId
            const title = conv.title || t('chat.newChat')
            const msgCount = conv.messages.length
            return (
              <div
                key={conv.id}
                className={`group flex items-start gap-2 px-3 py-2.5 border-b border-[#0e1a26] cursor-pointer transition-colors ${
                  isActive ? 'bg-[var(--fd-bg-input-focus)]' : 'hover:bg-[var(--fd-bg-elev)]'
                }`}
                onClick={() => onSelect(conv.id)}
              >
                {/* Active indicator */}
                <div className={`w-1 h-1 rounded-full mt-1.5 shrink-0 ${isActive ? 'bg-[var(--color-accent)]' : 'bg-transparent'}`} />

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <p className={`text-[11px] font-medium leading-tight truncate ${isActive ? 'text-[#c8d8ea]' : 'text-[#7a9ab8]'}`}>
                    {title}
                  </p>
                  <p className="text-[9px] text-[#3a5070] mt-0.5">
                    {formatDate(conv.createdAt)} · {msgCount} {t('chat.historyMsgs', { count: msgCount })}
                  </p>
                </div>

                {/* Delete */}
                <button
                  type="button"
                  onClick={e => { e.stopPropagation(); deleteConversation(conv.id) }}
                  className="opacity-0 group-hover:opacity-100 p-1 text-[#3a5070] hover:text-[#ff6b6b] transition-all shrink-0"
                  title="Delete"
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="square">
                    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
                  </svg>
                </button>
              </div>
            )
          })
        )}
      </div>

      {/* Clear all */}
      {sorted.length > 0 && (
        <div className="px-3 py-2 border-t border-[var(--fd-rule)] shrink-0">
          <button
            type="button"
            onClick={handleClearAll}
            className="w-full text-[10px] text-[#3a5070] hover:text-[#ff6b6b] transition-colors py-1"
          >
            {t('chat.historyDeleteAll')}
          </button>
        </div>
      )}
    </div>
  )
}
