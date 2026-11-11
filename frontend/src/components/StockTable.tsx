import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import clsx from 'clsx'
import { type Stock, resolveStockName } from '../api/client'
import { useWatchlist } from '../hooks/useStocks'
import { useLLMContext } from '../contexts/useLLMContext'
import SetAlertModal from './SetAlertModal'
import { useAuth } from '../auth/useAuth'

/** Compact star for table row — filled when watching */
function StarIcon({ filled }: { filled: boolean }) {
  return filled ? (
    <svg className="w-3.5 h-3.5 text-[var(--color-accent)] shrink-0" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </svg>
  ) : (
    <svg className="w-3.5 h-3.5 text-[var(--fd-text-faint)] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="square" strokeLinejoin="miter" strokeWidth={1.5}
        d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
    </svg>
  )
}

/** Sort arrow indicator — shows ▲ / ▼ / ⇅ based on active column */
function SortArrow({ col, sortCol, sortDir }: { col: string; sortCol: string; sortDir: string }) {
  if (sortCol !== col) {
    return <span className="text-[var(--color-accent)] ml-1 select-none">⇅</span>
  }
  return (
    <span className="text-[var(--color-accent)] ml-1 select-none">
      {sortDir === 'asc' ? '▲' : '▼'}
    </span>
  )
}

interface StockTableProps {
  stocks: Stock[]
  isLoading?: boolean
  isFiltered?: boolean
  /** Current sort column — passed from StockList via URL */
  sortCol: string
  /** Current sort direction — passed from StockList via URL */
  sortDir: 'asc' | 'desc'
  /** Called when user clicks a column header — StockList updates URL */
  onSort: (col: string) => void
}

export default function StockTable({ stocks, isLoading, isFiltered, sortCol, sortDir, onSort }: StockTableProps) {
  const { t, i18n } = useTranslation()
  const { isWatching, toggle } = useWatchlist()
  const { analyzeFocusedStock, focusedSymbol } = useLLMContext()
  const { isAuthenticated } = useAuth()
  const [alertStock, setAlertStock] = useState<Stock | null>(null)

  const sorted = useMemo(() => {
    return [...stocks].sort((a, b) => {
      let va: string | number = ''
      let vb: string | number = ''

      switch (sortCol) {
        case 'symbol':     va = a.symbol;      vb = b.symbol;      break
        case 'name':       va = resolveStockName(a.name, a.name_cn, i18n.language); vb = resolveStockName(b.name, b.name_cn, i18n.language); break
        case 'price':      va = a.price ?? 0;  vb = b.price ?? 0;  break
        case 'change':     va = a.change_percent ?? 0; vb = b.change_percent ?? 0; break
        case 'volume':     va = a.volume ?? 0;  vb = b.volume ?? 0;  break
        case 'market_cap':va = a.market_cap ?? 0; vb = b.market_cap ?? 0; break
        case 'sector':     va = a.sector || ''; vb = b.sector || ''; break
      }

      if (va < vb) return sortDir === 'asc' ? -1 : 1
      if (va > vb) return sortDir === 'asc' ? 1 : -1
      return 0
    })
  }, [stocks, sortCol, sortDir, i18n.language])

  const formatCurrency = (val: number | null) => {
    if (val == null) return '—'
    return val.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
  }

  const formatPercent = (val: number | null) => {
    if (val == null) return '—'
    const sign = val >= 0 ? '+' : ''
    return `${sign}${val.toFixed(2)}%`
  }

  const formatVolume = (val: number | null) => {
    if (val == null) return '—'
    if (val >= 1e9) return `${(val / 1e9).toFixed(1)}B`
    if (val >= 1e6) return `${(val / 1e6).toFixed(1)}M`
    if (val >= 1e3) return `${(val / 1e3).toFixed(1)}K`
    return val.toString()
  }

  const formatMarketCap = (val: number | null) => {
    if (val == null) return '—'
    if (val >= 1e12) return `$${(val / 1e12).toFixed(1)}T`
    if (val >= 1e9) return `$${(val / 1e9).toFixed(1)}B`
    if (val >= 1e6) return `$${(val / 1e6).toFixed(2)}M`
    return `$${val.toLocaleString()}`
  }

  /* ── Sortable TH ─────────────────────────────────────────────────────────── */
  const th = (col: string, label: string, align: string = 'left') => (
    <th
      onClick={() => onSort(col)}
      className={clsx(
        'table-th px-4 py-3 cursor-pointer select-none hover:text-[var(--fd-text-primary)] transition-colors',
        'hover:bg-[var(--fd-bg-hover)]',
        align === 'right' ? 'text-right' : 'text-left'
      )}
    >
      {label}
      <SortArrow col={col} sortCol={sortCol} sortDir={sortDir} />
    </th>
  )

  if (isLoading) {
    return (
      <div className="bg-surface-card border border-border overflow-hidden">
        <div className="animate-pulse p-4">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="flex gap-4 py-3 border-b border-[var(--fd-rule)] last:border-0">
              <div className="h-3 bg-[var(--fd-rule)] w-14" />
              <div className="h-3 bg-[var(--fd-rule)] flex-1" />
              <div className="h-3 bg-[var(--fd-rule)] w-18" />
              <div className="h-3 bg-[var(--fd-rule)] w-14" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (stocks.length === 0) {
    return (
      <div className="bg-surface-card border border-border p-8 text-center">
        <p className="text-[var(--fd-text-dim)] text-sm">
          {isFiltered ? t('table.noDataFiltered') : t('table.noData')}
        </p>
      </div>
    )
  }

  return (
    <>
    <div className="bg-surface-card border border-border overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-[var(--fd-rule)]">
            <tr className="text-[var(--fd-text-dim)] text-xs font-semibold tracking-widest uppercase">
              {/* Star column — not sortable */}
              <th className="table-th px-4 py-3 w-8" />
              {/* AI analyze column — not sortable */}
              <th className="table-th px-4 py-3 w-8" />
              {/* Alert bell column — not sortable, auth only */}
              {isAuthenticated && <th className="table-th px-4 py-3 w-8" />}
              {th('symbol',    t('table.symbol'))}
              {th('name',      t('table.name'))}
              {th('price',     t('table.price'),      'right')}
              {th('change',    t('table.change'),      'right')}
              {th('volume',    t('table.volume'),      'right')}
              {th('market_cap',t('table.mktCap'),       'right')}
              {th('sector',    t('table.sector'))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--fd-rule)]">
            {sorted.map((stock) => {
              const isPositive = stock.change != null && stock.change >= 0
              const isNeutral = stock.change == null || stock.change === 0

              return (
                <tr
                  key={stock.id}
                  className={`transition-colors ${focusedSymbol === stock.symbol ? 'bg-[var(--fd-bg-elev)] hover:bg-[var(--fd-bg-hover)]' : 'hover:bg-[var(--fd-bg-elev)]'}`}
                >
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggle(stock.symbol)}
                      className="hover:scale-110 transition-transform"
                      aria-label={isWatching(stock.symbol) ? t('watchlist.removeFromWatchlist') : t('watchlist.addToWatchlist')}
                    >
                      <StarIcon filled={isWatching(stock.symbol)} />
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => analyzeFocusedStock(stock.symbol)}
                      className={`hover:scale-110 transition-transform ${focusedSymbol === stock.symbol ? 'text-[var(--color-accent)]' : 'text-[var(--fd-text-faint)] hover:text-[var(--color-accent)]'}`}
                      aria-label={`Analyze ${stock.symbol} with AI`}
                      title={`Analyze ${stock.symbol} with FlowDesktop AI`}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 3 L13.5 8.5 L19 10 L13.5 11.5 L12 17 L10.5 11.5 L5 10 L10.5 8.5 Z" />
                        <path d="M5 3 L5.75 5.25 L8 6 L5.75 6.75 L5 9 L4.25 6.75 L2 6 L4.25 5.25 Z" />
                      </svg>
                    </button>
                  </td>
                  {isAuthenticated && (
                    <td className="px-4 py-3">
                      <button
                        onClick={() => setAlertStock(stock)}
                        className="text-[var(--fd-text-faint)] hover:text-amber-400 transition-colors hover:scale-110"
                        aria-label={`Set alert for ${stock.symbol}`}
                        title={t('alerts.setAlertFor') + ' ' + stock.symbol}
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="square">
                          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                        </svg>
                      </button>
                    </td>
                  )}
                  <td className="px-4 py-3">
                    <Link
                      to={`/stock/${stock.symbol}`}
                      className="font-semibold text-[var(--color-accent)] hover:text-[var(--color-nova)]"
                    >
                      {stock.symbol}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-[var(--fd-text-secondary)] max-w-[200px] truncate">
                    {resolveStockName(stock.name, stock.name_cn, i18n.language)}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold text-[var(--fd-text-primary)]">
                    {formatCurrency(stock.price ?? null)}
                  </td>
                  <td
                    className={clsx(
                      'px-4 py-3 text-right font-semibold',
                      isNeutral ? 'text-[var(--fd-text-dim)]' : isPositive ? 'text-[var(--color-stock-up)]' : 'text-[var(--color-stock-down)]'
                    )}
                  >
                    {formatPercent(stock.change_percent ?? null)}
                  </td>
                  <td className="px-4 py-3 text-right text-[var(--fd-text-dim)] hidden sm:table-cell">
                    {formatVolume(stock.volume ?? null)}
                  </td>
                  <td className="px-4 py-3 text-right text-[var(--fd-text-dim)] hidden md:table-cell">
                    {formatMarketCap(stock.market_cap ?? null)}
                  </td>
                  <td className="px-4 py-3 text-[var(--fd-text-dim)] hidden lg:table-cell">
                    {stock.sector ? t('sectors.' + stock.sector) : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>

    {alertStock && (
      <SetAlertModal
        symbol={alertStock.symbol}
        exchange={alertStock.exchange}
        currentPrice={alertStock.price ?? null}
        onClose={() => setAlertStock(null)}
      />
    )}
    </>
  )
}
