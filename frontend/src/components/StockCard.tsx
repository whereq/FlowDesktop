import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import clsx from 'clsx'
import { resolveStockName } from '../api/client'
import { useWatchlist } from '../hooks/useStocks'

interface StockCardProps {
  symbol: string
  name: string
  name_cn?: string | null
  price: number | null
  change: number | null | undefined
  changePercent: number | null | undefined
  volume?: number | null | undefined
}

/** Star icon — filled amber when watching, outline when not */
function StarIcon({ filled }: { filled: boolean }) {
  return filled ? (
    <svg className="w-4 h-4 text-[var(--color-accent)]" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </svg>
  ) : (
    <svg className="w-4 h-4 text-[var(--fd-text-faint)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="square" strokeLinejoin="miter" strokeWidth={1.5}
        d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
    </svg>
  )
}

export default function StockCard({
  symbol,
  name,
  name_cn,
  price,
  change,
  changePercent,
  volume,
}: StockCardProps) {
  const { t, i18n } = useTranslation()
  const { isWatching, toggle } = useWatchlist()
  const displayName = resolveStockName(name, name_cn, i18n.language)
  const watched = isWatching(symbol)
  const isPositive = change != null && change >= 0
  const isNeutral = change == null || change === 0

  const formatCurrency = (val: number | null | undefined) => {
    if (val == null) return '—'
    return val.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    })
  }

  const formatPercent = (val: number | null | undefined) => {
    if (val == null) return '—'
    const sign = val >= 0 ? '+' : ''
    return `${sign}${val.toFixed(2)}%`
  }

  const formatVolume = (val: number | null | undefined) => {
    if (val == null) return '—'
    if (val >= 1_000_000_000) return `${(val / 1_000_000_000).toFixed(1)}B`
    if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`
    if (val >= 1_000) return `${(val / 1_000).toFixed(1)}K`
    return val.toString()
  }

  return (
    <Link
      to={`/stock/${symbol}`}
      className="block bg-surface-card border border-border px-3 py-2 hover:bg-[var(--fd-bg-hover)] transition-colors relative group"
    >
      {/* Top row: symbol + name (left) | price + change (right) */}
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="min-w-0">
          <h3 className="font-semibold text-[var(--fd-text-primary)] text-sm leading-tight">{symbol}</h3>
          <p className="text-[var(--fd-text-dim)] text-[10px] truncate max-w-[120px] leading-tight">{displayName}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="font-semibold text-[var(--fd-text-primary)] text-sm leading-tight">{formatCurrency(price)}</p>
          <p
            className={clsx(
              'text-xs font-semibold leading-tight',
              isNeutral ? 'text-[var(--fd-text-dim)]' : isPositive ? 'text-[var(--color-stock-up)]' : 'text-[var(--color-stock-down)]'
            )}
          >
            {formatPercent(changePercent)}
          </p>
        </div>
      </div>

      {/* Bottom row: volume (left) | star toggle (right) */}
      <div className="flex items-center justify-between mt-1">
        {volume != null ? (
          <span className="text-[10px] text-[var(--fd-text-dim)] tracking-widest uppercase leading-tight">
            {t('watchlist.vol')} {formatVolume(volume)}
          </span>
        ) : <span />}
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); toggle(symbol) }}
          className="p-0.5 hover:scale-110 transition-transform"
          aria-label={watched ? t('watchlist.removeFromWatchlist') : t('watchlist.addToWatchlist')}
        >
          <StarIcon filled={watched} />
        </button>
      </div>
    </Link>
  )
}
