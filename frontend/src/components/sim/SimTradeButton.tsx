import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/useAuth'
import { useSimAccounts } from '../../hooks/useSim'
import OrderTicket from './OrderTicket'

/**
 * StockDetail entry point into the simulator. If the signed-in user has a
 * paper-trading account in the stock's currency, opens a pre-filled order ticket;
 * otherwise links to the Simulator to set one up.
 */
export default function SimTradeButton({ symbol, currency }: { symbol: string; currency?: string | null }) {
  const { t } = useTranslation()
  const { isAuthenticated } = useAuth()
  const { data: accounts } = useSimAccounts()
  const [open, setOpen] = useState(false)

  if (!isAuthenticated) return null
  const match = currency ? (accounts ?? []).find((a) => a.currency === currency) : undefined

  const cls = 'text-[11px] px-2 py-1 border border-[var(--color-accent)] text-[var(--color-accent)] hover:bg-[var(--color-accent)]/10'

  if (!match) {
    return <Link to="/simulator" className={cls}>{t('sim.tradeSetup', 'Trade in simulator')} ↗</Link>
  }
  return (
    <>
      <button onClick={() => setOpen(true)} className={cls}>{t('sim.tradeSimulated', 'Trade (simulated)')}</button>
      {open && (
        <OrderTicket accountId={match.id} currency={match.currency}
          presetSymbol={symbol} initialSide="buy" onClose={() => setOpen(false)} />
      )}
    </>
  )
}
