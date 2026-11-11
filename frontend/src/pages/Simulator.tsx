import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import { Panel, Sparkline } from '../components/ui'
import { useSimAccounts, useSimAccount, useSimOrders, useSimSnapshots } from '../hooks/useSim'
import { api, type SimAccountSummary } from '../api/client'
import OrderTicket from '../components/sim/OrderTicket'

const CURRENCIES = ['USD', 'HKD', 'CNY', 'JPY', 'CAD', 'SGD', 'TWD', 'KRW']
const fmt = (s: string | null | undefined) =>
  s == null ? '—' : Number(s).toLocaleString(undefined, { maximumFractionDigits: 2 })
const signCls = (n: number) => (n > 0 ? 'text-green-400' : n < 0 ? 'text-rose-400' : 'text-[var(--fd-text-dim)]')

function CreateAccount({ onCreated }: { onCreated: (a: SimAccountSummary) => void }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [currency, setCurrency] = useState('USD')
  const [balance, setBalance] = useState('100000')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const input = 'text-xs bg-[var(--fd-bg)] border border-[var(--fd-rule)] px-2 py-1.5 text-[var(--fd-text)] outline-none focus:border-[var(--color-accent)]'

  const create = async () => {
    setErr(''); setBusy(true)
    try {
      const a = await api.createSimAccount({ name: name.trim() || `${currency} paper`, currency, initial_balance: balance })
      qc.invalidateQueries({ queryKey: ['sim-accounts'] })
      onCreated(a)
    } catch (e) {
      const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setErr(d ?? t('sim.createFailed', 'Could not create account'))
    } finally { setBusy(false) }
  }

  return (
    <Panel label={t('sim.newAccount', 'New simulator account')}>
      <div className="flex flex-col gap-2 max-w-sm">
        <input className={input} placeholder={t('sim.accountName', 'Account name')} value={name} onChange={(e) => setName(e.target.value)} />
        <div className="flex gap-2">
          <select className={input + ' flex-1'} value={currency} onChange={(e) => setCurrency(e.target.value)}>
            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input className={input + ' flex-1'} inputMode="numeric" placeholder={t('sim.startingCash', 'Starting cash')}
            value={balance} onChange={(e) => setBalance(e.target.value)} />
        </div>
        <p className="text-[10px] text-[var(--fd-text-faint)]">
          {t('sim.currencyHint', 'You can only trade stocks in this currency’s markets (e.g. USD → NYSE/NASDAQ, CNY → SSE/SZSE).')}
        </p>
        {err && <div className="text-[11px] text-amber-500">{err}</div>}
        <button onClick={create} disabled={busy}
          className="text-xs py-1.5 border border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)] disabled:opacity-50">
          {busy ? t('sim.creating', 'Creating…') : t('sim.create', 'Create account')}
        </button>
      </div>
    </Panel>
  )
}

function Dashboard({ accountId }: { accountId: number }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const { data: acct } = useSimAccount(accountId)
  const { data: orders } = useSimOrders(accountId)
  const { data: snaps } = useSimSnapshots(accountId)
  const [ticket, setTicket] = useState<{ symbol?: string; side: 'buy' | 'sell' } | null>(null)

  if (!acct) return <Panel><span className="text-xs text-[var(--fd-text-faint)]">{t('common.loading', 'Loading…')}</span></Panel>

  const curveVals = (snaps ?? []).map((s) => Number(s.equity))
  const norm = curveVals.length >= 2
    ? (() => { const lo = Math.min(...curveVals), hi = Math.max(...curveVals); const d = hi - lo || 1; return curveVals.map((v) => ((v - lo) / d) * 100) })()
    : []
  const openOrders = (orders ?? []).filter((o) => o.status === 'pending')
  const recentOrders = (orders ?? []).filter((o) => o.status !== 'pending').slice(0, 8)

  const cancel = async (oid: number) => {
    await api.cancelSimOrder(accountId, oid).catch(() => {})
    qc.invalidateQueries({ queryKey: ['sim-orders', accountId] })
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Equity header */}
      <Panel label={`${acct.name} · ${acct.currency}`}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-wrap gap-6">
            <Stat label={t('sim.equity', 'Equity')} value={`${fmt(acct.equity)} ${acct.currency}`} big />
            <Stat label={t('sim.totalReturn', 'Total return')}
              value={`${fmt(acct.total_return)} (${acct.total_return_pct}%)`} cls={signCls(acct.total_return_pct)} />
            <Stat label={t('sim.dayChange', 'Day change')}
              value={`${fmt(acct.day_change)} (${acct.day_change_pct}%)`} cls={signCls(acct.day_change_pct)} />
            <Stat label={t('sim.cash', 'Cash')} value={fmt(acct.cash_balance)} />
          </div>
          <button onClick={() => setTicket({ side: 'buy' })}
            className="text-xs py-1.5 px-3 border border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]">
            + {t('sim.trade', 'Trade')}
          </button>
        </div>
        {norm.length >= 2 && (
          <div className="mt-2 text-[var(--color-accent)]"><Sparkline values={norm} w={320} h={40} fill /></div>
        )}
      </Panel>

      {/* Positions */}
      <Panel label={t('sim.positions', 'Positions')}>
        {acct.positions.length === 0 ? (
          <span className="text-xs text-[var(--fd-text-faint)]">{t('sim.noPositions', 'No positions yet — place a trade.')}</span>
        ) : (
          <table className="w-full border-collapse text-[11px]">
            <thead><tr className="text-[9px] uppercase tracking-wider text-[var(--fd-text-faint)]">
              <Th>{t('sim.symbol', 'Symbol')}</Th><Th>{t('sim.qty', 'Qty')}</Th><Th>{t('sim.avgCost', 'Avg')}</Th>
              <Th>{t('sim.price', 'Price')}</Th><Th>{t('sim.value', 'Value')}</Th><Th>{t('sim.pnl', 'P&L')}</Th>
              <Th>{t('sim.weight', 'Wt%')}</Th><Th> </Th>
            </tr></thead>
            <tbody>
              {acct.positions.map((p) => (
                <tr key={p.symbol} className="border-t border-[var(--fd-rule)] text-[var(--fd-text-dim)]">
                  <Td><span className="font-mono text-[var(--fd-text)]">{p.symbol}</span></Td>
                  <Td>{fmt(p.quantity)}</Td><Td>{fmt(p.avg_cost)}</Td><Td>{fmt(p.price)}</Td><Td>{fmt(p.market_value)}</Td>
                  <Td><span className={signCls(p.unrealized_pnl_pct)}>{fmt(p.unrealized_pnl)} ({p.unrealized_pnl_pct}%)</span></Td>
                  <Td>{p.weight_pct}%</Td>
                  <Td><button onClick={() => setTicket({ symbol: p.symbol, side: 'sell' })}
                    className="text-[10px] text-rose-400 hover:underline">{t('sim.sell', 'Sell')}</button></Td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {/* Orders */}
      {(openOrders.length > 0 || recentOrders.length > 0) && (
        <Panel label={t('sim.orders', 'Orders')}>
          <div className="flex flex-col gap-1 text-[11px]">
            {openOrders.map((o) => (
              <div key={o.id} className="flex items-center justify-between border-b border-[var(--fd-rule)] py-1">
                <span className="text-[var(--fd-text-dim)]">
                  <span className="text-amber-400">●</span> {o.side} {fmt(o.quantity)} <span className="font-mono text-[var(--fd-text)]">{o.symbol}</span> {o.order_type}
                  {o.limit_price ? ` @${fmt(o.limit_price)}` : ''} · {o.status}
                </span>
                <button onClick={() => cancel(o.id)} className="text-[10px] text-rose-400 hover:underline">{t('sim.cancel', 'Cancel')}</button>
              </div>
            ))}
            {recentOrders.map((o) => (
              <div key={o.id} className="flex items-center justify-between py-0.5 text-[var(--fd-text-faint)]">
                <span>{o.side} {fmt(o.quantity)} <span className="font-mono">{o.symbol}</span> · {o.status}
                  {o.status === 'filled' && o.avg_fill_price ? ` @${fmt(o.avg_fill_price)}` : ''}
                  {o.reject_reason ? ` (${o.reject_reason})` : ''}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {ticket && (
        <OrderTicket accountId={accountId} currency={acct.currency}
          presetSymbol={ticket.symbol} initialSide={ticket.side} onClose={() => setTicket(null)} />
      )}
    </div>
  )
}

function Stat({ label, value, big, cls }: { label: string; value: string; big?: boolean; cls?: string }) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-wider text-[var(--fd-text-faint)]">{label}</div>
      <div className={`font-mono ${big ? 'text-lg' : 'text-[13px]'} ${cls ?? 'text-[var(--fd-text)]'}`}>{value}</div>
    </div>
  )
}
const Th = ({ children }: { children: ReactNode }) => <th className="text-left font-semibold py-1 pr-2">{children}</th>
const Td = ({ children }: { children: ReactNode }) => <td className="py-1 pr-2 align-top">{children}</td>

export default function Simulator() {
  const { t } = useTranslation()
  const { data: accounts, isLoading } = useSimAccounts()
  const [selected, setSelected] = useState<number | null>(null)
  const list = accounts ?? []
  const selectedId = selected ?? list[0]?.id ?? null
  const [creating, setCreating] = useState(false)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-bold tracking-widest uppercase text-[var(--fd-text)]">{t('sim.title', 'Trading Simulator')}</h1>
        {list.length > 0 && (
          <button onClick={() => setCreating((c) => !c)} className="text-[11px] text-[var(--color-accent)] hover:underline">
            + {t('sim.newAccountShort', 'New account')}
          </button>
        )}
      </div>

      {list.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {list.map((a) => (
            <button key={a.id} onClick={() => { setSelected(a.id); setCreating(false) }}
              className={`text-[11px] px-2 py-1 border ${a.id === selectedId && !creating
                ? 'border-[var(--color-accent)] text-[var(--color-accent)] bg-[var(--fd-bg-elev)]'
                : 'border-[var(--fd-rule)] text-[var(--fd-text-dim)] hover:text-[var(--fd-text)]'}`}>
              {a.name} · {a.currency}
            </button>
          ))}
        </div>
      )}

      {isLoading && <span className="text-xs text-[var(--fd-text-faint)]">{t('common.loading', 'Loading…')}</span>}
      {!isLoading && (creating || list.length === 0) && (
        <CreateAccount onCreated={(a) => { setSelected(a.id); setCreating(false) }} />
      )}
      {!creating && selectedId != null && <Dashboard accountId={selectedId} />}
    </div>
  )
}
