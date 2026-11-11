import { useParams, Link } from 'react-router-dom'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { resolveStockName } from '../api/client'
import { useStock, useHistoricalPrices, useWatchlist, useStockRelationships } from '../hooks/useStocks'
import PriceChart from '../components/PriceChart'
import EventChips from '../components/EventChips'
import AiAnalysisPanel from '../components/AiAnalysisPanel'
import MarketSignalsPanel from '../components/MarketSignalsPanel'
import SimTradeButton from '../components/sim/SimTradeButton'
import { Panel, Delta, FlagChip } from '../components/ui'
import { format, subDays, subMonths, subYears } from 'date-fns'

type TimeRange = '1W' | '1M' | '3M' | '6M' | '1Y'
const RANGES: TimeRange[] = ['1W', '1M', '3M', '6M', '1Y']
const DATE_FMT = 'yyyy-MM-dd'

function exchangeToFlag(exchange?: string | null): string {
  if (!exchange) return 'us'
  const map: Record<string, string> = {
    NYQ: 'us', NMS: 'us', NGM: 'us', BTS: 'us', NYSE: 'us', NASDAQ: 'us',
    TSX: 'ca', SSE: 'cn', SZSE: 'cn', HK: 'hk', HKEX: 'hk',
    JPX: 'jp', SGX: 'sg', TAI: 'tw', KSC: 'kr',
  }
  return map[exchange] || 'us'
}

export default function StockDetail() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const locale = lang === 'zh' ? 'zh-CN' : 'en-US'
  const { symbol } = useParams<{ symbol: string }>()
  const [timeRange, setTimeRange] = useState<TimeRange>('3M')

  const getRange = (): { startDate: string; endDate: string } => {
    const end = new Date()
    let start: Date
    if      (timeRange === '1W') start = subDays(end, 7)
    else if (timeRange === '3M') start = subMonths(end, 3)
    else if (timeRange === '6M') start = subMonths(end, 6)
    else if (timeRange === '1Y') start = subYears(end, 1)
    else                          start = subMonths(end, 1)
    return { startDate: format(start, DATE_FMT), endDate: format(end, DATE_FMT) }
  }

  const { startDate, endDate } = getRange()
  const { data: stock, isLoading: sLoad } = useStock(symbol || '')
  const { data: historicalData, isLoading: hLoad } = useHistoricalPrices(symbol || '', startDate, endDate)
  const { data: relationships } = useStockRelationships(symbol || '')
  const { isWatching, toggle } = useWatchlist()

  const fmt$ = (v: number | null) => v == null ? '—' : v.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  const fmtVol = (v: number | null) => {
    if (v == null) return '—'
    if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`
    if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`
    if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`
    return v.toLocaleString(locale)
  }
  const fmtMCap = (v: number | null) => {
    if (v == null) return '—'
    if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`
    if (v >= 1e9)  return `$${(v / 1e9).toFixed(2)}B`
    if (v >= 1e6)  return `$${(v / 1e6).toFixed(2)}M`
    return `$${v.toLocaleString(locale)}`
  }

  if (sLoad) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 256 }}>
      <div style={{ width: 24, height: 24, border: '2px solid var(--color-accent)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
    </div>
  )

  if (!stock) return (
    <div style={{ textAlign: 'center', padding: '48px 0' }}>
      <h2 style={{ fontSize: 20, fontWeight: 600, color: 'var(--fd-text)', marginBottom: 8 }}>{t('stock.notFound')}</h2>
      <p style={{ color: 'var(--fd-text-dim)', marginBottom: 24 }}>{t('stock.notFoundHint', { symbol })}</p>
      <Link to="/" style={{ padding: '8px 20px', background: 'var(--color-accent)', color: '#0A0B0D', fontWeight: 600, fontSize: 13, textDecoration: 'none' }}>
        {t('stock.backToDashboard')}
      </Link>
    </div>
  )

  const pos = stock.change != null && stock.change >= 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontFamily: 'var(--font-ui)' }}>
      {/* Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--fd-text-faint)', fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.1em' }}>
        <Link to="/" style={{ color: 'var(--fd-text-dim)', textDecoration: 'none' }}>{lang === 'zh' ? '概览' : 'DASHBOARD'}</Link>
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6" /></svg>
        <span style={{ color: 'var(--fd-text)' }}>{stock.symbol}</span>
      </div>

      {/* Stock Header */}
      <Panel>
        <div className="grid md:grid-cols-[2fr_1fr] gap-5">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <FlagChip code={exchangeToFlag(stock.exchange)} />
              <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 28, fontWeight: 500, color: 'var(--fd-text)', letterSpacing: '-0.01em' }}>
                {stock.symbol}
              </h1>
              <span style={{ color: 'var(--fd-text-dim)', fontSize: 14 }}>· {resolveStockName(stock.name, stock.name_cn, lang)}</span>
              {stock.exchange && (
                <span style={{ marginLeft: 6, padding: '2px 6px', border: '1px solid var(--fd-rule)', fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--fd-text-faint)', letterSpacing: '0.1em' }}>
                  {stock.exchange}
                </span>
              )}
              <button
                onClick={() => toggle(stock.symbol)}
                style={{ marginLeft: 4, background: 'transparent', border: 'none', cursor: 'pointer', color: isWatching(stock.symbol) ? '#facc15' : 'var(--fd-text-faint)' }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill={isWatching(stock.symbol) ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.5">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                </svg>
              </button>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 10 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 36, fontWeight: 500, color: 'var(--fd-text)' }}>
                {fmt$(stock.price ?? null)}
              </span>
              {stock.change_percent != null && <Delta value={stock.change_percent} size={15} />}
              <span style={{ color: 'var(--fd-text-faint)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                {lang === 'zh' ? '近实时' : 'near-realtime'}
              </span>
            </div>
            <div style={{ marginTop: 10 }}>
              <SimTradeButton symbol={stock.symbol} currency={stock.currency} />
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
              {[
                [lang === 'zh' ? '市值' : 'MKT CAP', fmtMCap(stock.market_cap ?? null)],
                [lang === 'zh' ? '成交量' : 'VOL', fmtVol(stock.volume ?? null)],
                [lang === 'zh' ? '板块' : 'SECTOR', stock.sector ? t('sectors.' + stock.sector) : '—'],
              ].map(([k, v]) => (
                <span key={k as string} style={{
                  display: 'inline-flex', flexDirection: 'column', padding: '4px 10px',
                  border: '1px solid var(--fd-rule)',
                }}>
                  <span style={{ color: 'var(--fd-text-faint)', fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.1em' }}>{k}</span>
                  <span style={{ color: 'var(--fd-text)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>{v}</span>
                </span>
              ))}
            </div>
            <EventChips symbol={stock.symbol} />
          </div>

          {/* Related stocks / quick actions */}
          {relationships && relationships.length > 0 && (
            <div style={{ border: '1px dashed var(--fd-rule)', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ color: 'var(--fd-text-faint)', fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.1em' }}>
                {lang === 'zh' ? '相关股票' : 'RELATED STOCKS'}
              </div>
              {relationships.slice(0, 5).map(rel => (
                <Link
                  key={rel.symbol}
                  to={`/stock/${rel.symbol}`}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6, padding: '6px 8px',
                    border: '1px solid var(--fd-rule)',
                    color: 'var(--fd-text)', fontSize: 12, textDecoration: 'none',
                  }}
                >
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-nova)' }}>{rel.symbol}</span>
                  {rel.strength != null && (
                    <span style={{
                      marginLeft: 'auto',
                      fontFamily: 'var(--font-mono)', fontSize: 10,
                      color: rel.direction === 'positive' ? 'var(--color-stock-up)' : 'var(--color-stock-down)',
                    }}>
                      {rel.direction === 'positive' ? '+' : '−'}{(rel.strength * 100).toFixed(0)}%
                    </span>
                  )}
                </Link>
              ))}
            </div>
          )}
        </div>
      </Panel>

      {/* Chart */}
      <div className="grid md:grid-cols-[2fr_1fr] gap-3">
        <Panel
          label={lang === 'zh' ? '价格走势' : 'Price history'}
          right={
            <div style={{ display: 'flex', gap: 2 }}>
              {RANGES.map(r => (
                <button
                  key={r}
                  onClick={() => setTimeRange(r)}
                  style={{
                    padding: '2px 6px',
                    fontFamily: 'var(--font-mono)', fontSize: 10,
                    color: timeRange === r ? 'var(--fd-text)' : 'var(--fd-text-faint)',
                    background: timeRange === r ? 'var(--fd-active-bg)' : 'transparent',
                    border: 'none', cursor: 'pointer',
                  }}
                >
                  {t(`chart.${r.toLowerCase()}`)}
                </button>
              ))}
            </div>
          }
        >
          <PriceChart data={historicalData || []} isLoading={hLoad} />
        </Panel>

        {/* Key Statistics */}
        <Panel label={lang === 'zh' ? '关键数据' : 'Key statistics'}>
          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', rowGap: 8, columnGap: 14 }}>
            {[
              [lang === 'zh' ? '板块' : 'Sector', stock.sector ? t('sectors.' + stock.sector) : '—'],
              [lang === 'zh' ? '行业' : 'Industry', stock.industry || '—'],
              [lang === 'zh' ? '市值' : 'Market cap', fmtMCap(stock.market_cap ?? null)],
              [lang === 'zh' ? '成交量' : 'Volume', fmtVol(stock.volume ?? null)],
              [lang === 'zh' ? '交易所' : 'Exchange', stock.exchange || '—'],
              [lang === 'zh' ? '涨跌额' : 'Change', stock.change != null ? `${pos ? '+' : ''}$${stock.change.toFixed(2)}` : '—'],
              [lang === 'zh' ? '涨跌幅' : 'Change %', stock.change_percent != null ? `${stock.change_percent >= 0 ? '+' : ''}${stock.change_percent.toFixed(2)}%` : '—'],
            ].map(([k, v]) => (
              <div key={k as string} style={{ display: 'contents' }}>
                <span style={{ color: 'var(--fd-text-dim)', fontSize: 12, fontFamily: 'var(--font-ui)' }}>{k}</span>
                <span style={{ color: 'var(--fd-text)', fontFamily: 'var(--font-mono)', fontSize: 12, textAlign: 'right' }}>{v}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {/* Market signals: insider / short interest / congress / filings (self-hide when empty) */}
      <MarketSignalsPanel symbol={stock.symbol} />

      {/* AI Analysis */}
      <AiAnalysisPanel symbol={stock.symbol} />
    </div>
  )
}
