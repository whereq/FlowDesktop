import { useState, useMemo, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import StockCard from './StockCard'
import StockTable from './StockTable'
import ExchangeFilter from './ExchangeFilter'
import Btn from './Btn'
import type { Stock } from '../api/client'

type SortCol = 'symbol' | 'name' | 'price' | 'change' | 'volume' | 'market_cap' | 'sector'

interface StockListProps {
  stocks: Stock[]
  isLoading?: boolean
  /** Heading text for the section */
  heading?: string
  /** Available exchange codes for the filter dropdown */
  exchanges: string[]
  /** Sector options (from useSectors hook) */
  sectors?: string[]
  /** Currently selected exchanges — controlled by parent */
  selectedExchanges: string[]
  onToggleExchange: (ex: string) => void
  onClearExchanges: () => void
  /** Currently selected sector — controlled by parent */
  selectedSector: string | undefined
  onSectorChange: (sector: string | undefined) => void
  /** True when a filter is active (drives empty-state message) */
  isFiltered?: boolean
  /** Extra controls rendered after the view-mode toggle (e.g. add-symbol form) */
  actions?: ReactNode
}

/** Generic stock listing section: filter bar + table/cards view, shared by Dashboard and Watchlist. */
export default function StockList({
  stocks,
  isLoading,
  heading,
  exchanges,
  sectors,
  selectedExchanges,
  onToggleExchange,
  onClearExchanges,
  selectedSector,
  onSectorChange,
  isFiltered,
  actions,
}: StockListProps) {
  const { t } = useTranslation()
  const [viewMode, setViewMode] = useState<'table' | 'cards'>('table')

  // Sort state in URL (shareable) + sessionStorage (survives remounts)
  const [searchParams, setSearchParams] = useSearchParams()
  const urlCol = searchParams.get('sort') as SortCol | null
  const urlDir = searchParams.get('dir') as 'asc' | 'desc' | null

  const _ssCol: SortCol = (sessionStorage.getItem('fd_sort_col') as SortCol) || 'symbol'
  const _ssDir: 'asc' | 'desc' = (sessionStorage.getItem('fd_sort_dir') as 'asc' | 'desc') || 'asc'

  // URL wins if present; sessionStorage is the fallback
  const sortCol: SortCol = urlCol || _ssCol
  const sortDir: 'asc' | 'desc' = urlDir || _ssDir

  const handleSort = (col: string) => {
    const nextDir: 'asc' | 'desc' = sortCol === col && sortDir === 'asc' ? 'desc' : 'asc'
    sessionStorage.setItem('fd_sort_col', col)
    sessionStorage.setItem('fd_sort_dir', nextDir)
    setSearchParams({ sort: col, dir: nextDir })
  }

  // Defensively deduplicate stocks by id (backend join can produce duplicates)
  const uniqueStocks = useMemo(() => {
    const seen = new Set<number>()
    return (stocks || []).filter((s) => {
      if (seen.has(s.id)) return false
      seen.add(s.id)
      return true
    })
  }, [stocks])

  // Defensively deduplicate sector options
  const uniqueSectors = useMemo(
    () => [...new Set(sectors || [])],
    [sectors]
  )

  return (
    <div className="space-y-1">
      {/* Filter bar + heading */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-2 gap-4">
        {heading && (
          <h2 className="text-sm font-bold tracking-widest uppercase text-[var(--fd-text-secondary)] border-l-2 border-[var(--color-accent)] pl-3 leading-none">
            {heading}
          </h2>
        )}

        <div className="flex items-center gap-3 flex-wrap">
          {/* Exchange Multi-Select */}
          {exchanges.length > 0 && (
            <ExchangeFilter
              exchanges={exchanges}
              selected={selectedExchanges}
              onToggle={onToggleExchange}
              onClear={onClearExchanges}
            />
          )}

          {/* Sector Filter */}
          {uniqueSectors.length > 0 && (
            <select
              value={selectedSector || ''}
              onChange={(e) => onSectorChange(e.target.value || undefined)}
              className="sector-select bg-[var(--fd-bg-elevated)] border border-border px-3 py-1.5 text-[var(--fd-text-secondary)] text-sm focus:outline-none focus:bg-[var(--fd-bg-input-focus)] transition-colors cursor-pointer"
            >
              <option value="">{t('filter.allSectors')}</option>
              {uniqueSectors.map((s) => (
                <option key={s} value={s}>{t('sectors.' + s)}</option>
              ))}
            </select>
          )}

          {/* View Mode Toggle */}
          <div className="flex bg-[var(--fd-bg-elevated)] p-px">
            {(['table', 'cards'] as const).map((mode) => (
              <Btn
                key={mode}
                onClick={() => setViewMode(mode)}
                variant="ghost"
                highlight={viewMode === mode}
                size="sm"
                className="view-btn w-[60px] min-w-[60px]"
              >
                {t(mode === 'table' ? 'filter.viewTable' : 'filter.viewCards')}
              </Btn>
            ))}
          </div>

          {/* Extra controls (e.g. add-symbol form for Watchlist) */}
          {actions}
        </div>
      </div>

      {/* Listing */}
      {viewMode === 'table'
        ? (
          <StockTable
            stocks={uniqueStocks}
            isLoading={isLoading}
            isFiltered={isFiltered}
            sortCol={sortCol}
            sortDir={sortDir}
            onSort={handleSort}
          />
        )
        : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-px bg-[var(--fd-rule)] border border-border">
            {isLoading
              ? [...Array(Math.min(uniqueStocks.length || 12, 12))].map((_, i) => (
                  <div key={i} className="bg-surface-card px-3 py-2 animate-pulse h-20" />
                ))
              : uniqueStocks.map((stock) => (
                  <StockCard key={stock.id} symbol={stock.symbol} name={stock.name} name_cn={stock.name_cn} price={stock.price ?? null} change={stock.change} changePercent={stock.change_percent} volume={stock.volume} />
                ))
            }
          </div>
        )
      }
    </div>
  )
}
