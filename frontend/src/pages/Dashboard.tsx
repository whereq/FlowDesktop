import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useStocks, useMarketOverview, useShowcaseStocks, useSectorThemes, useAlerts, useExchanges, useSectors } from '../hooks/useStocks'
import { resolveStockName } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { Panel, Delta, FlagChip, Sparkline, generateSparkline } from '../components/ui'
import StockList from '../components/StockList'
import UpcomingEventsWidget from '../components/UpcomingEventsWidget'
import PulseEnableBanner from '../components/PulseEnableBanner'
import { useWatchlistContext } from '../contexts/useWatchlistContext'

/** Map exchange code → country flag code for FlagChip */
function exchangeToFlag(exchange?: string | null): string {
  if (!exchange) return 'us'
  const map: Record<string, string> = {
    NYQ: 'us', NMS: 'us', NGM: 'us', BTS: 'us', NYSE: 'us', NASDAQ: 'us',
    TSX: 'ca', SSE: 'cn', SZSE: 'cn', HK: 'hk', HKEX: 'hk',
    JPX: 'jp', SGX: 'sg', TAI: 'tw', KSC: 'kr',
  }
  return map[exchange] || 'us'
}

// ── Sector Heatmap ───────────────────────────────────────────────────────────

function SectorHeatmap({ lang }: { lang: string }) {
  const { data: themes } = useSectorThemes('static_gics')
  const withSentiment = (themes || []).filter(th => th.avg_sentiment != null)
  if (withSentiment.length === 0) return null

  const colorFor = (chg: number) => {
    if (chg >= 0.15) return '#2EA86D'
    if (chg >= 0.05) return '#388F5E'
    if (chg >= 0)    return '#2B5C44'
    if (chg >= -0.05) return '#7A3A3A'
    if (chg >= -0.15) return '#A33D3D'
    return '#C84545'
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {withSentiment.map(s => (
        <Link
          key={s.id}
          to="/sectors"
          style={{
            flex: '1 1 110px',
            background: colorFor(s.avg_sentiment ?? 0),
            color: '#fff',
            padding: 10,
            minHeight: 64,
            display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
            textDecoration: 'none',
          }}
        >
          <span style={{ fontSize: 11.5, fontWeight: 600 }}>
            {lang === 'zh' && s.name_cn ? s.name_cn : s.name}
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
            {(s.avg_sentiment ?? 0) >= 0 ? '+' : ''}{(s.avg_sentiment ?? 0).toFixed(2)}
          </span>
        </Link>
      ))}
    </div>
  )
}

// ── Triggered Alerts Widget ──────────────────────────────────────────────────

function TriggeredAlertsWidget() {
  const { t } = useTranslation()
  const { data: alerts = [], rearmAlert, deleteAlert } = useAlerts()
  const triggered = alerts.filter((a) => !a.is_active && a.triggered_at !== null)
  if (triggered.length === 0) return null

  return (
    <Panel
      label={t('alerts.triggered')}
      right={<Link to="/watchlist" style={{ color: 'var(--fd-text-faint)', fontSize: 10, fontFamily: 'var(--font-mono)', textDecoration: 'none' }}>{t('alerts.manageAlerts')} →</Link>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {triggered.map(a => {
          const isPct = a.alert_type.includes('change_pct')
          const val = isPct
            ? `${a.threshold > 0 ? '+' : ''}${a.threshold}%`
            : a.threshold.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
          return (
            <div key={a.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '8px 0', borderBottom: '1px solid var(--fd-rule)' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-accent)' }} />
                  <span style={{ color: 'var(--fd-text)', fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600 }}>{a.symbol}</span>
                </div>
                <p style={{ color: 'var(--fd-text-dim)', fontSize: 11, marginTop: 2 }}>
                  {t(`alerts.type_${a.alert_type}`)} <span style={{ color: 'var(--fd-text)' }}>{val}</span>
                </p>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button onClick={() => rearmAlert(a.id)} style={{ fontSize: 10, padding: '2px 8px', border: '1px solid var(--fd-rule)', color: 'var(--color-nova)', background: 'transparent' }}>
                  {t('alerts.rearm')}
                </button>
                <button onClick={() => deleteAlert(a.id)} style={{ color: 'var(--fd-text-faint)', background: 'transparent', border: 'none', padding: 2 }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </Panel>
  )
}

// ── Mover Card ───────────────────────────────────────────────────────────────

function MoversCard({ title, accent, stocks, lang }: {
  title: string
  accent: string
  stocks: Array<{ symbol: string; name: string; name_cn?: string | null; price: number | null; change_percent?: number | null }>
  lang: string
}) {
  return (
    <Panel
      label={title}
      right={<span style={{ width: 4, height: 4, borderRadius: 99, background: accent, display: 'inline-block' }} />}
      noBody
    >
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {stocks.map((s, i) => (
          <Link
            key={s.symbol}
            to={`/stock/${s.symbol}`}
            style={{
              display: 'grid', gridTemplateColumns: 'auto 1fr auto auto', gap: 8, alignItems: 'center',
              padding: '8px 12px',
              borderBottom: i < stocks.length - 1 ? '1px solid var(--fd-rule)' : 'none',
              textDecoration: 'none', color: 'inherit',
            }}
          >
            <span style={{ width: 18, color: 'var(--fd-text-faint)', fontFamily: 'var(--font-mono)', fontSize: 10 }}>
              {(i + 1).toString().padStart(2, '0')}
            </span>
            <div>
              <div style={{ color: 'var(--fd-text)', fontFamily: 'var(--font-mono)', fontSize: 11.5 }}>{s.symbol}</div>
              <div style={{ color: 'var(--fd-text-dim)', fontSize: 11, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {resolveStockName(s.name, s.name_cn, lang)}
              </div>
            </div>
            <span style={{ color: 'var(--fd-text)', fontFamily: 'var(--font-mono)', fontSize: 11.5 }}>
              {s.price != null ? s.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
            </span>
            {s.change_percent != null && <Delta value={s.change_percent} size={11} withArrow={false} />}
          </Link>
        ))}
      </div>
    </Panel>
  )
}

// ── ShowcaseDashboard (unauthenticated) ──────────────────────────────────────

function ShowcaseDashboard() {
  const { t } = useTranslation()
  const { login, register } = useAuth()

  const [selectedSector, setSelectedSector] = useState<string | undefined>()
  const [selectedExchanges, setSelectedExchanges] = useState<string[]>([])

  // Filter server-side (see FullDashboard) — the showcase endpoint returns a
  // curated set or the top matches for the selected exchange/sector.
  const { data: filteredStocks, isLoading } = useShowcaseStocks({
    exchanges: selectedExchanges.length > 0 ? selectedExchanges : undefined,
    sector: selectedSector,
  })
  const { data: dbExchanges } = useExchanges()
  const { data: sectors } = useSectors()

  const exchanges = [...new Set([...ALL_EXCHANGES, ...(dbExchanges || [])])].sort()

  const toggleExchange = (ex: string) =>
    setSelectedExchanges((prev) =>
      prev.includes(ex) ? prev.filter((e) => e !== ex) : [...prev, ex]
    )

  const isFiltered = !!(selectedSector || selectedExchanges.length > 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Sign-up CTA */}
      <Panel>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '12px 0', textAlign: 'center' }}>
          <p style={{ color: 'var(--fd-text)', fontSize: 14, fontWeight: 600 }}>{t('dashboard.ctaTitle')}</p>
          <p style={{ color: 'var(--fd-text-dim)', fontSize: 12 }}>{t('dashboard.ctaSubtitle')}</p>
          <div style={{ display: 'flex', gap: 12 }}>
            <button onClick={login} style={{ padding: '8px 20px', fontSize: 13, fontWeight: 600, background: 'var(--color-accent)', color: '#0A0B0D', border: 'none' }}>
              {t('auth.signIn')}
            </button>
            <button onClick={register} style={{ padding: '8px 20px', fontSize: 13, fontWeight: 600, color: 'var(--color-accent)', background: 'transparent', border: '1px solid var(--color-accent)' }}>
              {t('auth.signUp')}
            </button>
          </div>
        </div>
      </Panel>

      {/* All Stocks — with Exchange/Sector filter bar + Table/Cards toggle */}
      <StockList
        stocks={filteredStocks || []}
        isLoading={isLoading}
        heading={t('dashboard.allStocks')}
        exchanges={exchanges}
        sectors={sectors}
        selectedExchanges={selectedExchanges}
        onToggleExchange={toggleExchange}
        onClearExchanges={() => setSelectedExchanges([])}
        selectedSector={selectedSector}
        onSectorChange={setSelectedSector}
        isFiltered={isFiltered}
      />
    </div>
  )
}

// ── Full Dashboard (authenticated) ───────────────────────────────────────────

/** Static list of all supported exchanges — merged with DB data to avoid gaps */
const ALL_EXCHANGES = ['NYQ', 'NMS', 'NGM', 'BTS', 'TSX', 'SSE', 'SZSE']

function FullDashboard() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language

  const [selectedSector, setSelectedSector] = useState<string | undefined>()
  const [selectedExchanges, setSelectedExchanges] = useState<string[]>([])

  // Filter server-side: the DB holds ~22k symbols and list_stocks caps at 500
  // ordered by symbol, so numeric Asian tickers (000…, 6xx…) fill the cap and
  // US stocks never arrive for client-side filtering. Pushing exchange/sector
  // to the API returns the right rows for any filter. The API expands code
  // variants (NYQ→NYSE, NMS→NASDAQ) so either form matches the stored codes.
  const { data: filteredStocks, isLoading: stocksLoading } = useStocks({
    limit: 500,
    exchanges: selectedExchanges.length > 0 ? selectedExchanges : undefined,
    sector: selectedSector,
  })
  // Small unfiltered sample for the watchlist preview widget.
  const { data: stocks } = useStocks({ limit: 6 })
  const { symbols: watchSymbols } = useWatchlistContext()
  const { data: marketOverview, isLoading: marketLoading } = useMarketOverview()
  const { data: dbExchanges } = useExchanges()
  const { data: sectors } = useSectors()

  const exchanges = [...new Set([...ALL_EXCHANGES, ...(dbExchanges || [])])].sort()

  const toggleExchange = (ex: string) =>
    setSelectedExchanges((prev) =>
      prev.includes(ex) ? prev.filter((e) => e !== ex) : [...prev, ex]
    )

  const isFiltered = !!(selectedSector || selectedExchanges.length > 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontFamily: 'var(--font-ui)' }}>
      {/* NOVA Pulse push-adoption CTA (self-hides when subscribed/dismissed) */}
      <PulseEnableBanner />
      {/* Market Indices */}
      {!marketLoading && marketOverview && marketOverview.indices.length > 0 && (
        <Panel label={lang === 'zh' ? '市场指数' : 'Market indices'} noBody>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5" style={{ borderTop: '1px solid var(--fd-rule)' }}>
            {marketOverview.indices.map((x) => (
              <div key={x.symbol} style={{
                padding: 12,
                borderRight: '1px solid var(--fd-rule)',
                borderBottom: '1px solid var(--fd-rule)',
              }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fd-text-faint)', letterSpacing: '0.1em' }}>{x.symbol}</span>
                  <span style={{ color: 'var(--fd-text-dim)', fontSize: 10 }}>{x.name}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginTop: 4 }}>
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--fd-text)', fontSize: 16, fontWeight: 500 }}>
                    {x.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                  {x.change_percent != null && <Delta value={x.change_percent} size={11} />}
                </div>
                <div style={{ marginTop: 4 }}>
                  <Sparkline
                    values={generateSparkline(x.symbol.charCodeAt(0), 24, (x.change_percent ?? 0) > 0 ? 0.6 : -0.6)}
                    color={(x.change_percent ?? 0) >= 0 ? 'var(--color-stock-up)' : 'var(--color-stock-down)'}
                    h={20} w={140} fill
                  />
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Top Gainers / Losers + Watchlist */}
      {!marketLoading && marketOverview && (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
          {/* Watchlist */}
          <Panel
            label={lang === 'zh' ? '我的观察列表' : 'My watchlist'}
            noBody
          >
            <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--font-ui)' }}>
              <thead>
                <tr style={{ color: 'var(--fd-text-faint)', fontSize: 9.5, letterSpacing: '0.1em', fontWeight: 600 }}>
                  {(lang === 'zh' ? ['代码', '名称', '最新', '涨跌'] : ['TICKER', 'NAME', 'LAST', 'CHG']).map((h, i) => (
                    <th key={i} style={{ padding: '8px 10px', borderBottom: '1px solid var(--fd-rule)', textAlign: i < 2 ? 'left' : 'right', fontWeight: 600 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(stocks || []).slice(0, 6).map(s => (
                  <tr key={s.symbol} style={{ borderBottom: '1px solid var(--fd-rule)' }}>
                    <td style={{ padding: '8px 10px' }}>
                      <Link to={`/stock/${s.symbol}`} style={{ display: 'flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}>
                        <FlagChip code={exchangeToFlag(s.exchange)} />
                        <span style={{ color: 'var(--fd-text)', fontFamily: 'var(--font-mono)', fontSize: 11.5, fontWeight: 500 }}>{s.symbol}</span>
                      </Link>
                    </td>
                    <td style={{ padding: '8px 10px', color: 'var(--fd-text-dim)', fontSize: 12, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {resolveStockName(s.name, s.name_cn, lang)}
                    </td>
                    <td style={{ padding: '8px 10px', textAlign: 'right', color: 'var(--fd-text)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                      {s.price != null ? s.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                    </td>
                    <td style={{ padding: '8px 10px', textAlign: 'right' }}>
                      {s.change_percent != null && <Delta value={s.change_percent} size={11} withArrow={false} />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          {/* Top gainers / losers */}
          {marketOverview.top_gainers.length > 0 && (
            <MoversCard
              title={lang === 'zh' ? '今日上涨' : 'Top gainers'}
              accent="var(--color-stock-up)"
              stocks={marketOverview.top_gainers.slice(0, 5)}
              lang={lang}
            />
          )}
          {marketOverview.top_losers.length > 0 && (
            <MoversCard
              title={lang === 'zh' ? '今日下跌' : 'Top losers'}
              accent="var(--color-stock-down)"
              stocks={marketOverview.top_losers.slice(0, 5)}
              lang={lang}
            />
          )}
        </div>
      )}

      {/* Triggered alerts */}
      <TriggeredAlertsWidget />

      {/* Upcoming earnings/dividends for the user's watchlist */}
      <UpcomingEventsWidget symbols={watchSymbols} />

      {/* Sector Heatmap */}
      <Panel
        label={lang === 'zh' ? '板块热力' : 'Sector heat'}
        right={<span style={{ color: 'var(--fd-text-faint)', fontFamily: 'var(--font-mono)', fontSize: 9.5 }}>
          {lang === 'zh' ? '颜色=今日情绪' : 'color = today sentiment'}
        </span>}
      >
        <SectorHeatmap lang={lang} />
      </Panel>

      {/* All Stocks — with Exchange/Sector filter bar + Table/Cards toggle */}
      <StockList
        stocks={filteredStocks || []}
        isLoading={stocksLoading}
        heading={t('dashboard.allStocks')}
        exchanges={exchanges}
        sectors={sectors}
        selectedExchanges={selectedExchanges}
        onToggleExchange={toggleExchange}
        onClearExchanges={() => setSelectedExchanges([])}
        selectedSector={selectedSector}
        onSectorChange={setSelectedSector}
        isFiltered={isFiltered}
      />
    </div>
  )
}

// ── Dashboard ────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? <FullDashboard /> : <ShowcaseDashboard />
}
