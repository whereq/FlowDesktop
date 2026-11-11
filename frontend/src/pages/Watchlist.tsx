import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useWatchlist, useStocks, useExchanges, useSectors } from '../hooks/useStocks'
import StockList from '../components/StockList'
import AlertsPanel from '../components/AlertsPanel'
import Btn from '../components/Btn'

type Tab = 'watchlist' | 'alerts'

/** Static list of all supported exchanges — merged with DB data to avoid gaps */
const ALL_EXCHANGES = ['NYQ', 'NMS', 'NGM', 'BTS', 'TSX', 'SSE', 'SZSE']

export default function Watchlist() {
  const { t, i18n } = useTranslation()
  const locale = i18n.language === 'zh' ? 'zh-CN' : 'en-US'
  const { symbols: watchlist, toggle } = useWatchlist()
  const [tab, setTab] = useState<Tab>('watchlist')
  const [selectedSector, setSelectedSector] = useState<string | undefined>()
  const [selectedExchanges, setSelectedExchanges] = useState<string[]>([])
  const [newSymbol, setNewSymbol] = useState('')

  // Fetch full stock data for watchlist symbols
  const { data: stocks, isLoading: stocksLoading } = useStocks({
    symbols: watchlist.length > 0 ? watchlist : undefined,
    limit: 500,
  })
  const { data: dbExchanges } = useExchanges()
  const { data: sectors } = useSectors()

  const exchanges = [...new Set([...ALL_EXCHANGES, ...(dbExchanges || [])])].sort()

  // Apply client-side sector + exchange filters to watchlist stocks
  const filteredStocks = (stocks || []).filter((s) => {
    if (selectedSector && s.sector !== selectedSector) return false
    if (selectedExchanges.length > 0 && !selectedExchanges.includes(s.exchange || '')) return false
    return true
  })

  // Derive last updated from the most recent quote timestamp
  const latestTs = (stocks || []).reduce<string | null>((max, s) => {
    if (!s.quote_timestamp) return max
    if (!max) return s.quote_timestamp
    return s.quote_timestamp > max ? s.quote_timestamp : max
  }, null)

  const fmtTime = (v: string | null) =>
    v ? new Date(v).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' }) : '—'

  const toggleExchange = (ex: string) =>
    setSelectedExchanges((prev) =>
      prev.includes(ex) ? prev.filter((e) => e !== ex) : [...prev, ex]
    )

  const add         = (e: FormEvent) => { e.preventDefault(); const s = newSymbol.toUpperCase().trim(); if (s && !watchlist.includes(s)) { toggle(s); setNewSymbol('') } }
  const addDefaults = () => ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA'].forEach((s) => { if (!watchlist.includes(s)) toggle(s) })

  const isFiltered = !!(selectedSector || selectedExchanges.length > 0)

  return (
    <div className="space-y-6">
      {/* Tab bar */}
      <div className="flex border-b border-border">
        {(['watchlist', 'alerts'] as Tab[]).map((t_) => (
          <button
            key={t_}
            onClick={() => setTab(t_)}
            className={`px-5 py-2.5 text-sm font-semibold tracking-wide transition-colors border-b-2 -mb-px ${
              tab === t_
                ? 'border-[var(--color-accent)] text-[var(--fd-text-primary)]'
                : 'border-transparent text-[var(--fd-text-dim)] hover:text-[var(--fd-text-secondary)]'
            }`}
          >
            {t(`${t_}.tabLabel`)}
          </button>
        ))}
      </div>

      {/* Alerts tab */}
      {tab === 'alerts' && <AlertsPanel />}

      {/* Watchlist tab */}
      {tab === 'watchlist' && <>

      {/* Stats bar */}
      {watchlist.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-2 gap-px bg-[var(--fd-rule)] border border-border">
          {[
            { label: t('watchlist.statTotal'),   value: filteredStocks.length.toLocaleString() },
            { label: t('watchlist.statUpdated'), value: fmtTime(latestTs) },
          ].map(({ label, value }) => (
            <div key={label} className="bg-surface-card p-4">
              <p className="text-[var(--fd-text-dim)] text-xs font-semibold tracking-widest uppercase mb-1">{label}</p>
              <p className="text-xl font-semibold text-[var(--fd-text-primary)]">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Empty state — no watchlist symbols at all */}
      {watchlist.length === 0 && (
        <div className="text-center py-16 bg-surface-card border border-border">
          <svg className="mx-auto h-10 w-10 text-[var(--fd-text-faint)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="square" strokeLinejoin="miter" strokeWidth={1.5}
              d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
          </svg>
          <h3 className="mt-4 text-base font-semibold text-[var(--fd-text-secondary)]">{t('watchlist.empty')}</h3>
          <p className="mt-2 text-[var(--fd-text-dim)] text-sm">{t('watchlist.emptyHint')}</p>
          <div className="mt-4">
            <Btn variant="ghost" size="md" onClick={addDefaults}>{t('watchlist.addDefaults')}</Btn>
          </div>
        </div>
      )}

      {/* Stock listing (filter bar + table/cards) — hidden when watchlist is empty */}
      {watchlist.length > 0 && (
        <StockList
          stocks={filteredStocks}
          isLoading={stocksLoading}
          heading={t('watchlist.title')}
          exchanges={exchanges}
          sectors={sectors}
          selectedExchanges={selectedExchanges}
          onToggleExchange={toggleExchange}
          onClearExchanges={() => setSelectedExchanges([])}
          selectedSector={selectedSector}
          onSectorChange={setSelectedSector}
          isFiltered={isFiltered}
          actions={
            <form onSubmit={add} className="flex gap-2">
              <input
                type="text"
                value={newSymbol}
                onChange={(e) => setNewSymbol(e.target.value)}
                placeholder={t('watchlist.addSymbol')}
                className="bg-[var(--fd-bg-elevated)] border border-border px-3 py-1.5 text-[var(--fd-text-primary)] placeholder-[var(--fd-text-dim)] text-sm focus:outline-none focus:bg-[var(--fd-bg-input-focus)] transition-colors w-36"
              />
              <Btn type="submit" variant="primary" size="sm">{t('watchlist.add')}</Btn>
            </form>
          }
        />
      )}

      </>}
    </div>
  )
}
