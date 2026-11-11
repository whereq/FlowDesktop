import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { resolveStockName } from '../api/client'
import { useSearchStocks, useWatchlist } from '../hooks/useStocks'

export default function SearchBar({ disabled = false }: { disabled?: boolean }) {
  const { t, i18n } = useTranslation()
  const [query, setQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const { data: results, isLoading } = useSearchStocks(query)
  const { isWatching, toggle } = useWatchlist()

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node) &&
        !inputRef.current?.contains(event.target as Node)
      ) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = (symbol: string) => {
    setQuery('')
    setIsOpen(false)
    navigate(`/stock/${symbol}`)
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && results && results.length > 0) {
      handleSelect(results[0].symbol)
    }
    if (e.key === 'Escape') {
      setIsOpen(false)
      inputRef.current?.blur()
    }
  }

  return (
    <div className="relative">
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setIsOpen(true)
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={disabled ? t('search.signInRequired') : t('search.placeholder')}
          className={`w-full border px-4 pl-10 py-1.5 text-sm transition-colors ${
            disabled
              ? 'bg-[var(--fd-bg)] border-[var(--fd-rule)] text-[var(--fd-text-faint)] placeholder-[var(--fd-text-faint)] cursor-not-allowed'
              : 'bg-[var(--fd-bg-elevated)] border-border text-[var(--fd-text-primary)] placeholder-[var(--fd-text-dim)] focus:outline-none focus:bg-[var(--fd-bg-input-focus)]'
          }`}
        />
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <svg
            className="h-4 w-4 text-[var(--fd-text-dim)]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="square"
              strokeLinejoin="miter"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>
        {isLoading && query && (
          <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
            <div className="h-3 w-3 border-2 border-[var(--color-accent)] border-t-transparent animate-spin" />
          </div>
        )}
      </div>

      {/* Dropdown */}
      {isOpen && query && results && results.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-50 w-full mt-1 bg-surface-card border border-border max-h-60 overflow-auto"
        >
          {results.map((result) => (
            <div
              key={result.symbol}
              className="flex items-center justify-between px-4 py-2 hover:bg-surface-raised"
            >
              <button
                onClick={() => handleSelect(result.symbol)}
                className="flex-1 text-left text-sm"
              >
                <span className="font-semibold text-[var(--fd-text-primary)]">{result.symbol}</span>
                <span className="ml-2 text-[var(--fd-text-dim)]">{resolveStockName(result.name, result.name_cn, i18n.language)}</span>
                {result.exchange && (
                  <span className="ml-2 text-xs text-[var(--fd-text-faint)]">{result.exchange}</span>
                )}
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); toggle(result.symbol) }}
                className="ml-2 p-1 hover:scale-110 transition-transform shrink-0"
                aria-label={isWatching(result.symbol) ? t('watchlist.removeFromWatchlist') : t('watchlist.addToWatchlist')}
              >
                {isWatching(result.symbol) ? (
                  <svg className="w-4 h-4 text-[var(--color-accent)]" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4 text-[var(--fd-text-faint)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="square" strokeLinejoin="miter" strokeWidth={1.5}
                      d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                  </svg>
                )}
              </button>
            </div>
          ))}
        </div>
      )}

      {isOpen && query && results && results.length === 0 && !isLoading && (
        <div className="absolute z-50 w-full mt-1 bg-surface-card border border-border p-4 text-center text-[var(--fd-text-dim)] text-sm">
          {t('search.noResults')}
        </div>
      )}
    </div>
  )
}
