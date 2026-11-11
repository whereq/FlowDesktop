import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'
import { useLLMContext } from '../../contexts/useLLMContext'
import { COMMANDS, type Command } from './commands'
import { CommandIcon } from './CommandIcon'

// ── Component ─────────────────────────────────────────────────────────────────

interface CommandPaletteProps {
  initialCommand?: string
  disabled?: boolean
  onClose: () => void
  onPortfolioToggle: () => void
  onExecute?: (commandId: string) => void
}

type View = 'list' | 'symbol' | 'input'

// ── BackHeader — module-level component ───────────────────────────────────────

interface BackHeaderProps {
  title: string
  activeCommand: Command | null
  onBack: () => void
  onClose: () => void
}

function BackHeader({ title, activeCommand, onBack, onClose }: BackHeaderProps) {
  return (
    <div className="flex items-center gap-2.5 px-3 py-2 border-b border-[var(--fd-rule)]">
      <button onClick={onBack} className="text-[#3a5070] hover:text-[#6a90b0] transition-colors" title="Back">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="square">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </button>
      {activeCommand && (
        <span className="text-[var(--color-accent)]"><CommandIcon id={activeCommand.id} size={12} /></span>
      )}
      <span className="text-[11px] font-semibold text-[var(--fd-text-secondary)]">{title}</span>
      <button onClick={onClose} className="ml-auto text-[#3a5070] hover:text-[var(--fd-text-dim)] transition-colors">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
  )
}

export default function CommandPalette({
  initialCommand,
  disabled,
  onClose,
  onPortfolioToggle,
  onExecute,
}: CommandPaletteProps) {
  const { t } = useTranslation()
  const params = useParams()
  const {
    focusedSymbol, analyzeStock, runCommittee,
    compareStocks, buildStrategy, screenStocksAction, macroImpact,
  } = useLLMContext()

  // Symbol from URL or context — may be empty
  const contextSymbol = params.symbol || focusedSymbol || ''

  const [search, setSearch] = useState('')
  const [activeId, setActiveId] = useState<string | null>(initialCommand ?? null)
  // symbolValue = what the user is currently typing in the symbol input box
  // committedSymbol = confirmed after clicking "Next →"
  const [symbolValue, setSymbolValue] = useState('')
  const [committedSymbol, setCommittedSymbol] = useState('')
  const [inputValue, setInputValue] = useState('')

  const activeCommand = activeId ? COMMANDS.find(c => c.id === activeId) ?? null : null

  // Determine view:
  //   'symbol' — collecting a stock symbol (command requires one, none focused)
  //   'input'  — collecting command-specific text (compare target, strategy, screen query, macro event)
  //   'list'   — command list
  // resolvedSymbol uses only confirmed symbols — NOT symbolValue while the user is still typing
  const resolvedSymbol = contextSymbol || committedSymbol

  const view: View = (() => {
    if (!activeCommand) return 'list'
    if (activeCommand.requiresSymbol && !resolvedSymbol) return 'symbol'
    if (activeCommand.needsInput) return 'input'
    return 'list' // will execute immediately in useEffect
  })()

  const searchRef  = useRef<HTMLInputElement>(null)
  const symbolRef  = useRef<HTMLInputElement>(null)
  const inputRef   = useRef<HTMLInputElement>(null)

  // Auto-focus the right input as view changes
  useEffect(() => {
    if (view === 'symbol') { symbolRef.current?.focus(); return }
    if (view === 'input')  { inputRef.current?.focus(); return }
    searchRef.current?.focus()
  }, [view])

  function executeCommand(cmd: Command, sym: string, extra?: string) {
    if (disabled) return
    switch (cmd.id) {
      case 'analyze':   analyzeStock(sym); break
      case 'committee': runCommittee(sym); break
      case 'compare':   if (extra) compareStocks([sym, extra.toUpperCase().trim()]); break
      case 'strategy':  if (extra) buildStrategy(sym, extra.trim()); break
      case 'screen':    if (extra) screenStocksAction(extra.trim()); break
      case 'macro':     if (extra) macroImpact(extra.trim()); break
      case 'portfolio': onPortfolioToggle(); break
    }
    onExecute?.(cmd.id)
    onClose()
  }

  function handleSelect(cmd: Command) {
    if (disabled) return
    setActiveId(cmd.id)
    setSymbolValue('')
    setCommittedSymbol('')
    setInputValue('')
  }

  function handleSymbolSubmit() {
    const sym = symbolValue.trim().toUpperCase()
    if (!sym || !activeCommand) return
    if (activeCommand.needsInput) {
      setCommittedSymbol(sym)  // commit symbol → re-render transitions to 'input' view
    } else {
      executeCommand(activeCommand, sym)  // no extra input needed — fire directly
    }
  }

  function handleInputSubmit() {
    if (!activeCommand || !inputValue.trim()) return
    executeCommand(activeCommand, resolvedSymbol, inputValue)
  }

  function goBack() {
    setActiveId(null)
    setSymbolValue('')
    setCommittedSymbol('')
    setInputValue('')
  }

  const filteredCommands = search.trim()
    ? COMMANDS.filter(c =>
        c.label.toLowerCase().includes(search.toLowerCase()) ||
        c.description.toLowerCase().includes(search.toLowerCase())
      )
    : COMMANDS

  // ── Symbol collection view ──────────────────────────────────────────────────
  if (view === 'symbol' && activeCommand) {
    return (
      <div className="shrink-0 border-t border-[var(--fd-rule)] bg-[#090e15]">
        <BackHeader
          title={t(`commands.${activeCommand.id}.short`)}
          activeCommand={activeCommand}
          onBack={goBack}
          onClose={onClose}
        />
        <div className="px-3 py-2.5">
          <p className="text-[10px] text-[#7ab0d8] mb-2">{t('commands.enterSymbol')}</p>
          <div className="flex gap-2">
            <input
              ref={symbolRef}
              value={symbolValue}
              onChange={e => setSymbolValue(e.target.value.toUpperCase())}
              onKeyDown={e => {
                if (e.key === 'Enter') handleSymbolSubmit()
                if (e.key === 'Escape') onClose()
              }}
              placeholder="e.g. AAPL, 000858.SZ, 00700.HK"
              className="flex-1 bg-[#0e1520] border border-[var(--fd-rule)] text-[var(--fd-text-secondary)] text-xs px-2.5 py-1.5 focus:outline-none focus:bg-[var(--fd-bg-input-focus)] placeholder:text-[#4a7090] font-mono uppercase"
            />
            <button
              type="button"
              onClick={handleSymbolSubmit}
              disabled={!symbolValue.trim()}
              className="shrink-0 px-3 py-1.5 bg-[var(--color-accent)] hover:bg-[#106ebe] text-white text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {t('commands.nextBtn')}
            </button>
          </div>
          <p className="text-[9px] text-[#4a7090] mt-2">
            {t('commands.enterSymbolTip')}
          </p>
        </div>
      </div>
    )
  }

  // ── Command-specific input view ─────────────────────────────────────────────
  if (view === 'input' && activeCommand) {
    return (
      <div className="shrink-0 border-t border-[var(--fd-rule)] bg-[#090e15]">
        <BackHeader
          title={`${t(`commands.${activeCommand.id}.short`)}${resolvedSymbol ? ` — ${resolvedSymbol}` : ''}`}
          activeCommand={activeCommand}
          onBack={goBack}
          onClose={onClose}
        />
        <div className="px-3 py-2.5 flex gap-2">
          <input
            ref={inputRef}
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') handleInputSubmit()
              if (e.key === 'Escape') onClose()
            }}
            placeholder={t(`commands.${activeCommand.id}.input`)}
            className="flex-1 bg-[#0e1520] border border-[var(--fd-rule)] text-[var(--fd-text-secondary)] text-xs px-2.5 py-1.5 focus:outline-none focus:bg-[var(--fd-bg-input-focus)] placeholder:text-[#4a7090]"
          />
          <button
            type="button"
            onClick={handleInputSubmit}
            disabled={!inputValue.trim()}
            className="shrink-0 px-3 py-1.5 bg-[var(--color-accent)] hover:bg-[#106ebe] text-white text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {t('commands.runBtn')}
          </button>
        </div>
      </div>
    )
  }

  // ── Command list view ───────────────────────────────────────────────────────
  return (
    <div className="shrink-0 border-t border-[var(--fd-rule)] bg-[#090e15]">
      {/* Search */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--fd-rule)]">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#5a8aaa" strokeWidth="2" strokeLinecap="square">
          <circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          ref={searchRef}
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === 'Escape' && onClose()}
          placeholder={t('commands.searchPlaceholder')}
          className="flex-1 bg-transparent text-[var(--fd-text-secondary)] text-xs outline-none placeholder:text-[#4a7090]"
        />
        <button onClick={onClose} className="text-[#3a5070] hover:text-[var(--fd-text-dim)] transition-colors">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      {/* Commands — ALL always clickable */}
      <div className="overflow-y-auto thin-scrollbar-ai" style={{ maxHeight: 228 }}>
        {filteredCommands.length === 0 && (
          <p className="text-[10px] text-[#5a8aaa] text-center py-4">{t('commands.noMatches', { query: search })}</p>
        )}
        {filteredCommands.map(cmd => (
          <button
            key={cmd.id}
            type="button"
            onClick={() => handleSelect(cmd)}
            disabled={disabled}
            className="w-full flex items-center gap-3 px-3 py-2 text-left border-b border-[#0d1520] hover:bg-[var(--fd-bg-elev)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <span className="shrink-0 text-[var(--color-accent)]">
              <CommandIcon id={cmd.id} size={13} />
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-semibold text-[var(--fd-text-secondary)]">{t(`commands.${cmd.id}.short`)}</span>
                {cmd.requiresSymbol && contextSymbol && (
                  <span className="text-[10px] font-mono text-[var(--color-accent)]">{contextSymbol}</span>
                )}
                {cmd.requiresSymbol && !contextSymbol && (
                  <span className="text-[9px] text-[#5a8aaa] border border-[#2a4060] px-1 py-px">enter symbol</span>
                )}
              </div>
              <p className="text-[10px] text-[#5a8aaa] mt-0.5 leading-snug truncate">{t(`commands.${cmd.id}.desc`)}</p>
            </div>
            <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="#4a7090" strokeWidth="2" strokeLinecap="square" className="shrink-0">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </button>
        ))}
      </div>

      {/* Footer */}
      <div className="px-3 py-1.5 border-t border-[#0d1520]">
        <p className="text-[9px] text-[#5a8aaa]">
          {contextSymbol
            ? t('commands.symbolFocused', { symbol: contextSymbol })
            : t('commands.noSymbolFocused')
          }
        </p>
      </div>
    </div>
  )
}
