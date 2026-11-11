import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useLLMContext } from '../../contexts/useLLMContext'
import { api, type AgentInfo } from '../../api/client'

interface ChatInputProps {
  onSend: (content: string) => void
  onPaletteOpen: () => void
  disabled?: boolean
}

export default function ChatInput({ onSend, onPaletteOpen, disabled }: ChatInputProps) {
  const { t } = useTranslation()
  const { focusedSymbol, selectedAgent, setSelectedAgent } = useLLMContext()
  const [value, setValue] = useState('')
  const [suggestion, setSuggestion] = useState<AgentInfo | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Debounced agent suggestion as the user types (only when no agent is active).
  useEffect(() => {
    if (selectedAgent || value.trim().length < 8) { setSuggestion(null); return }
    const q = value
    const h = setTimeout(() => {
      api.suggestAgent(q).then(s => setSuggestion(s)).catch(() => setSuggestion(null))
    }, 400)
    return () => clearTimeout(h)
  }, [value, selectedAgent])

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 72) + 'px'
  }, [value])

  function handleSubmit() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    setSuggestion(null)
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // "/" at start of empty input → open command palette
    if (e.key === '/' && value === '') {
      e.preventDefault()
      onPaletteOpen()
      return
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const placeholder = focusedSymbol
    ? `Ask about ${focusedSymbol}...`
    : t('chat.placeholder')

  return (
    <div className="border-t-2 border-[var(--fd-rule)] bg-[var(--fd-bg)] shrink-0">
      {/* Agent suggestion chip — offer to run the typed request as a native agent */}
      {suggestion && !selectedAgent && (
        <button
          type="button"
          onClick={() => { setSelectedAgent(suggestion.name); setSuggestion(null) }}
          className="flex items-center gap-1.5 w-full px-3 py-1.5 border-b border-[var(--fd-rule)] bg-[var(--fd-bg-elev)] hover:bg-[var(--fd-bg-hover)] text-left"
          style={{ fontSize: 11 }}
        >
          <span>{suggestion.icon}</span>
          <span style={{ color: 'var(--color-nova)', fontWeight: 600 }}>
            {t('chat.runWith', 'Run with')} {suggestion.title}
          </span>
          <span style={{ color: 'var(--fd-text-faint)', marginLeft: 'auto', fontSize: 10 }}>
            {t('chat.runWithHint', 'scoped agent →')}
          </span>
        </button>
      )}
      <div className="flex items-stretch">
        {/* Command palette trigger — "/" button */}
        <button
          type="button"
          onClick={onPaletteOpen}
          disabled={disabled}
          title="Commands (or press / when input is empty)"
          className="shrink-0 w-9 flex items-center justify-center border-r border-[var(--fd-rule)] text-[var(--fd-text-faint)] hover:text-[var(--color-accent)] hover:bg-[var(--fd-bg-hover)] transition-colors disabled:opacity-30 disabled:cursor-not-allowed font-mono text-sm font-bold"
        >
          /
        </button>

        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="flex-1 bg-[var(--fd-bg)] border-0 text-[var(--fd-text-primary)] text-sm px-3 py-2.5 resize-none focus:outline-none focus:bg-[var(--fd-bg-input-focus)] transition-colors placeholder:text-[var(--fd-text-faint)] disabled:opacity-50"
          style={{ minHeight: 40, maxHeight: 80, overflowY: 'auto' }}
        />

        {/* Send button */}
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!value.trim() || disabled}
          className="shrink-0 w-11 flex items-center justify-center bg-[var(--color-accent)] hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label={t('chat.send')}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="square" strokeLinejoin="miter">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
    </div>
  )
}
