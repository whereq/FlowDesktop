import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Panel } from './ui'
import {
  useInsiderActivity, useShortInterest, useCongressTrades, useFilings,
} from '../hooks/useStocks'

const CODE_LABEL: Record<string, string> = {
  P: 'Buy', S: 'Sell', A: 'Grant', M: 'Exercise', F: 'Tax', G: 'Gift',
}

function num(n: number | null | undefined): string {
  if (n == null) return '—'
  return Math.round(n).toLocaleString()
}

function AskNova({ q }: { q: string }) {
  const { t } = useTranslation()
  return (
    <Link
      to={`/?ask=${encodeURIComponent(q)}`}
      className="text-[10px] text-[var(--color-nova)] hover:underline whitespace-nowrap"
    >
      {t('signals.askNova', 'Ask NOVA')} ↗
    </Link>
  )
}

const th = 'text-left font-semibold text-[var(--fd-text-faint)] uppercase tracking-wider text-[9px] py-1'
const td = 'py-1 pr-2 text-[11px] text-[var(--fd-text-dim)] align-top'

/**
 * StockDetail panels surfacing the alt-data NOVA ingests (insider Form 4, short
 * interest, congressional trades, SEC filings). Each sub-panel self-hides when the
 * symbol has no data (e.g. non-US names), so the section is quiet when empty.
 */
export default function MarketSignalsPanel({ symbol }: { symbol: string }) {
  const { t } = useTranslation()
  const insider = useInsiderActivity(symbol).data
  const short = useShortInterest(symbol).data
  const congress = useCongressTrades(symbol).data
  const filings = useFilings(symbol).data

  const hasInsider = insider && (insider.count ?? 0) > 0
  const hasShort = short && !short.note && (short.short_pct_float != null || short.days_to_cover != null)
  const hasCongress = congress && (congress.count ?? 0) > 0
  const hasFilings = filings && filings.filings.length > 0

  if (!hasInsider && !hasShort && !hasCongress && !hasFilings) return null

  return (
    <>
      {hasShort && (
        <Panel label={t('signals.shortInterest', 'Short interest')}>
          <div className="flex items-center justify-between">
            <div className="flex gap-6 text-[11px]">
              <div>
                <div className="text-[9px] uppercase tracking-wider text-[var(--fd-text-faint)]">% float short</div>
                <div className="text-[var(--fd-text)] font-mono text-[13px]">
                  {short!.short_pct_float != null ? `${short!.short_pct_float}%` : '—'}
                </div>
              </div>
              <div>
                <div className="text-[9px] uppercase tracking-wider text-[var(--fd-text-faint)]">Days to cover</div>
                <div className="text-[var(--fd-text)] font-mono text-[13px]">{short!.days_to_cover ?? '—'}</div>
              </div>
              <div>
                <div className="text-[9px] uppercase tracking-wider text-[var(--fd-text-faint)]">MoM shares</div>
                <div className={`font-mono text-[13px] ${(short!.shares_short_change_pct ?? 0) > 0 ? 'text-rose-400' : 'text-green-400'}`}>
                  {short!.shares_short_change_pct != null ? `${short!.shares_short_change_pct > 0 ? '+' : ''}${short!.shares_short_change_pct}%` : '—'}
                </div>
              </div>
            </div>
            <AskNova q={`How heavily shorted is ${symbol}, and is a squeeze likely?`} />
          </div>
          <div className="text-[9px] text-[var(--fd-text-faint)] mt-1">
            {short!.as_of ? `${t('chat.asOf', 'as of')} ${short!.as_of}` : ''} · {short!.source}
          </div>
        </Panel>
      )}

      {hasInsider && (
        <Panel label={t('signals.insider', 'Insider activity (Form 4)')}>
          <div className="flex items-center justify-between mb-1">
            <div className="text-[11px] text-[var(--fd-text-dim)]">
              {t('signals.netOpenMarket', 'Net open-market')}:{' '}
              <span className={`font-mono ${(insider!.summary?.net_open_market_shares ?? 0) >= 0 ? 'text-green-400' : 'text-rose-400'}`}>
                {num(insider!.summary?.net_open_market_shares)} sh
              </span>
            </div>
            <AskNova q={`Are insiders buying or selling ${symbol}? What does the Form 4 activity suggest?`} />
          </div>
          <table className="w-full border-collapse">
            <thead><tr>
              <th className={th}>Date</th><th className={th}>Insider</th>
              <th className={th}>Action</th><th className={th}>Shares</th><th className={th}>Price</th>
            </tr></thead>
            <tbody>
              {insider!.recent?.slice(0, 6).map((r, i) => (
                <tr key={i} className="border-t border-[var(--fd-rule)]">
                  <td className={td}>{r.date ?? '—'}</td>
                  <td className={td}>{r.insider}{r.title ? <span className="text-[var(--fd-text-faint)]"> · {r.title}</span> : ''}</td>
                  <td className={td}>{r.code ? (CODE_LABEL[r.code] ?? r.code) : '—'}</td>
                  <td className={td}>{num(r.shares)}</td>
                  <td className={td}>{r.price != null ? `$${r.price}` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      {hasCongress && (
        <Panel label={t('signals.congress', 'Congressional trades')}>
          <div className="flex items-center justify-between mb-1">
            <div className="text-[11px] text-[var(--fd-text-dim)]">
              <span className="text-green-400">{congress!.buys ?? 0} buys</span> ·{' '}
              <span className="text-rose-400">{congress!.sells ?? 0} sells</span>
            </div>
            <AskNova q={`Have any members of Congress traded ${symbol} recently?`} />
          </div>
          <table className="w-full border-collapse">
            <thead><tr>
              <th className={th}>Date</th><th className={th}>Member</th>
              <th className={th}>Type</th><th className={th}>Amount</th>
            </tr></thead>
            <tbody>
              {congress!.trades?.slice(0, 6).map((r, i) => (
                <tr key={i} className="border-t border-[var(--fd-rule)]">
                  <td className={td}>{r.transaction_date ?? '—'}</td>
                  <td className={td}>{r.politician}<span className="text-[var(--fd-text-faint)]"> · {r.chamber}</span></td>
                  <td className={td}>{r.type ?? '—'}</td>
                  <td className={td}>{r.amount ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-[9px] text-[var(--fd-text-faint)] mt-1">{congress!.source}</div>
        </Panel>
      )}

      {hasFilings && (
        <Panel label={t('signals.filings', 'SEC filings')}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-[var(--fd-text-dim)]">{t('signals.recentFilings', 'Recent 10-K / 10-Q')}</span>
            <AskNova q={`What did management flag in ${symbol}'s latest 10-K/10-Q?`} />
          </div>
          <div className="flex flex-col gap-1">
            {filings!.filings.slice(0, 6).map((f, i) => (
              <div key={i} className="flex items-center justify-between text-[11px] border-t border-[var(--fd-rule)] py-1">
                <span className="text-[var(--fd-text-dim)]">
                  <span className="font-mono text-[var(--fd-text)]">{f.form}</span> · {f.filing_date}
                </span>
                {f.url && (
                  <a href={f.url} target="_blank" rel="noopener noreferrer" className="text-[var(--color-accent)] hover:underline text-[10px]">
                    {t('signals.view', 'View')} ↗
                  </a>
                )}
              </div>
            ))}
          </div>
        </Panel>
      )}
    </>
  )
}
