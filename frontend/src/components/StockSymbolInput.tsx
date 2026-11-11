import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { resolveStockName, type SearchResult } from '../api/client'
import { useSearchStocks } from '../hooks/useStocks'

interface Props {
  value: string
  onChange: (symbol: string) => void
  onSelect?: (result: SearchResult) => void
  placeholder?: string
  className?: string
}

/**
 * A text input that shows a live stock-search dropdown as the user types.
 * On selection the symbol (e.g. "AAPL") is passed to onChange and the
 * dropdown closes. The user can also type a bare symbol and submit without
 * selecting from the list.
 */
export default function StockSymbolInput({ value, onChange, onSelect, placeholder = 'AAPL', className = '' }: Props) {
  const { i18n } = useTranslation()
  const [query, setQuery] = useState(value)
  const [open, setOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const { data: results = [], isLoading } = useSearchStocks(query)

  // Sync external value changes (e.g., form reset)
  useEffect(() => {
    setQuery(value)
  }, [value])

  // Close on outside click
  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (
        !inputRef.current?.contains(e.target as Node) &&
        !dropdownRef.current?.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [])

  const select = (result: SearchResult) => {
    setQuery(result.symbol)
    onChange(result.symbol)
    onSelect?.(result)
    setOpen(false)
    setActiveIdx(-1)
  }

  const handleChange = (raw: string) => {
    const upper = raw.toUpperCase()
    setQuery(upper)
    onChange(upper)          // keep parent in sync for plain-typed symbols too
    setOpen(true)
    setActiveIdx(-1)
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (!open || results.length === 0) {
      if (e.key === 'Escape') setOpen(false)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx((i) => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx((i) => Math.max(i - 1, -1))
    } else if (e.key === 'Enter') {
      if (activeIdx >= 0) {
        e.preventDefault()
        select(results[activeIdx])
      } else if (results.length > 0) {
        e.preventDefault()
        select(results[0])
      }
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const showDropdown = open && query.length >= 1

  return (
    <div className={`relative ${className}`}>
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => query.length >= 1 && setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          autoComplete="off"
          className="w-full bg-[var(--fd-bg-elevated)] border border-border pl-8 pr-3 py-1.5 text-[var(--fd-text-primary)] placeholder-[var(--fd-text-faint)] text-sm focus:outline-none focus:bg-[var(--fd-bg-input-focus)] transition-colors"
        />
        {/* search icon */}
        <div className="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none">
          {isLoading && query ? (
            <div className="h-3 w-3 border-2 border-[var(--color-accent)] border-t-transparent animate-spin" />
          ) : (
            <svg className="h-3.5 w-3.5 text-[var(--fd-text-dim)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="square" strokeLinejoin="miter" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          )}
        </div>
      </div>

      {/* Dropdown */}
      {showDropdown && results.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-50 left-0 right-0 mt-1 bg-surface-card border border-border max-h-52 overflow-auto shadow-lg"
        >
          {results.map((r, idx) => (
            <button
              key={r.symbol}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); select(r) }}
              className={`w-full text-left px-3 py-2 flex items-baseline gap-2 transition-colors ${
                idx === activeIdx ? 'bg-[var(--fd-bg-input-focus)]' : 'hover:bg-surface-raised'
              }`}
            >
              <span className="text-sm font-semibold text-[var(--fd-text-primary)] shrink-0">{r.symbol}</span>
              <span className="text-xs text-[var(--fd-text-dim)] truncate">
                {resolveStockName(r.name, r.name_cn, i18n.language)}
              </span>
              {r.exchange && (
                <span className="text-[10px] text-[#666] shrink-0 ml-auto">{r.exchange}</span>
              )}
            </button>
          ))}
        </div>
      )}

      {showDropdown && results.length === 0 && !isLoading && (
        <div className="absolute z-50 left-0 right-0 mt-1 bg-surface-card border border-border px-3 py-2 text-xs text-[var(--fd-text-dim)]">
          No results for "{query}"
        </div>
      )}
    </div>
  )
}
