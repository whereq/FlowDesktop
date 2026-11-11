import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/useAuth'
import { PAID_PLANS, type PlanConfig } from '../config/plans'
import { api } from '../api/client'
import keycloak from '../auth/keycloak'

// Free tier has no Stripe product — defined inline
const FREE_PLAN = {
  key: 'free',
  keycloakRole: null as string | null,
  highlight: false,
  price: '$0',
  pricePeriod: '',
  msgLimit: '10',
  featureKeys: ['free_f1', 'free_f2', 'free_f3'],
}

type AnyPlan = typeof FREE_PLAN | PlanConfig

function currentTier(roles: string[]): string | null {
  if (roles.includes('fd-admin')) return 'admin'
  if (roles.includes('fd-tier-unlimited')) return 'fd-tier-unlimited'
  if (roles.includes('fd-tier-2')) return 'fd-tier-2'
  if (roles.includes('fd-tier-1')) return 'fd-tier-1'
  if (roles.includes('fd-tier-byok')) return 'fd-tier-byok'
  return null // free trial
}

const ALL_PLANS: AnyPlan[] = [FREE_PLAN, ...PAID_PLANS]

export default function Pricing() {
  const { t } = useTranslation()
  const { isAuthenticated, roles } = useAuth()
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null)
  const [checkoutError, setCheckoutError] = useState<string | null>(null)
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null)
  const [upgraded, setUpgraded] = useState(false)

  useEffect(() => {
    if (checkoutUrl) {
      window.location.href = checkoutUrl
    }
  }, [checkoutUrl])

  // Returning from a successful Stripe Checkout (success_url=/pricing?upgraded=1).
  // The fd-tier role was just granted server-side; force a token refresh so it
  // applies immediately (entitlements + API calls pick up the new tier).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('upgraded') !== '1') return
    setUpgraded(true)
    keycloak.updateToken(9_999_999).catch(() => { /* user can re-login to refresh */ })
      .finally(() => window.history.replaceState({}, '', '/pricing'))
  }, [])

  const activeTier = isAuthenticated ? currentTier(roles) : null

  const handleUpgrade = async (plan: PlanConfig) => {
    if (!plan.stripePriceId) return
    setLoadingPlan(plan.key)
    setCheckoutError(null)
    try {
      const url = await api.createCheckoutSession(plan.stripePriceId, plan.keycloakRole)
      setCheckoutUrl(url)
    } catch {
      setCheckoutError(t('pricing.checkoutError'))
      setLoadingPlan(null)
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      {/* Heading */}
      <div className="text-center mb-10">
        <h1 className="text-2xl font-bold text-[var(--fd-text-primary)] tracking-tight">
          {t('pricing.title')}
        </h1>
        <p className="mt-2 text-sm text-[var(--fd-text-dim)]">{t('pricing.subtitle')}</p>
      </div>

      {upgraded && (
        <div className="mb-4 text-center text-sm font-medium px-4 py-3 rounded"
          style={{ background: 'var(--fd-bg-elev)', border: '1px solid var(--color-nova)', color: 'var(--color-nova)' }}>
          {t('pricing.upgradeSuccess', '🎉 Payment successful — your new plan is now active.')}
        </div>
      )}

      {/* Plan cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {ALL_PLANS.map((plan) => {
          const isActive =
            activeTier === null
              ? plan.keycloakRole === null
              : activeTier === plan.keycloakRole ||
                (activeTier === 'admin' && plan.key === 'unlimited')

          const stripePriceId = 'stripePriceId' in plan ? plan.stripePriceId : null

          return (
            <div
              key={plan.key}
              className={`relative flex flex-col rounded border ${
                plan.highlight
                  ? 'border-[var(--color-accent)] bg-[#0d1a2b]'
                  : 'border-border bg-surface-card'
              } p-5`}
            >
              {/* Recommended badge */}
              {plan.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-[var(--color-accent)] text-white text-[10px] font-bold uppercase tracking-wider rounded-full">
                  {t('pricing.recommended')}
                </div>
              )}

              {/* Active tier badge */}
              {isActive && isAuthenticated && (
                <div className="absolute top-3 right-3 px-2 py-0.5 bg-[#1a3a1a] border border-[#2d6a2d] text-green-400 text-[10px] font-semibold uppercase tracking-wide rounded">
                  {t('pricing.currentPlan')}
                </div>
              )}

              {/* Plan name */}
              <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--fd-text-secondary)]">
                {t(`pricing.plan_${plan.key}`)}
              </h2>

              {/* Price */}
              <div className="mt-3 flex items-end gap-1">
                <span className="text-3xl font-bold text-[var(--fd-text-primary)]">{plan.price}</span>
                {plan.pricePeriod && (
                  <span className="text-xs text-[#666] mb-1">{plan.pricePeriod}</span>
                )}
              </div>

              {/* Message limit */}
              <p className="mt-1 text-xs text-[#666]">
                {'msgLimitKey' in plan && plan.msgLimitKey
                  ? t(plan.msgLimitKey)
                  : t('pricing.msgLimit', { n: plan.msgLimit })}
              </p>

              <div className="my-4 border-t border-border" />

              {/* Features */}
              <ul className="flex-1 space-y-2">
                {plan.featureKeys.map((fk) => (
                  <li key={fk} className="flex items-start gap-2 text-xs text-[#aaa]">
                    <span className="text-[var(--color-accent)] mt-0.5 shrink-0">✓</span>
                    {t(`pricing.${fk}`)}
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <div className="mt-5">
                {plan.keycloakRole === null ? (
                  // Free tier
                  <div className="w-full py-2 text-center text-xs font-semibold text-[var(--fd-text-faint)] border border-border rounded cursor-default">
                    {isAuthenticated && isActive ? t('pricing.currentPlan') : t('pricing.getStarted')}
                  </div>
                ) : stripePriceId ? (
                  // Paid tier — Stripe price configured, checkout ready
                  <button
                    type="button"
                    disabled={!isAuthenticated || loadingPlan !== null}
                    onClick={() => handleUpgrade(plan as PlanConfig)}
                    className="w-full py-2 text-xs font-semibold text-white bg-[var(--color-accent)] hover:bg-[#006cbe] disabled:opacity-50 disabled:cursor-not-allowed rounded transition-colors"
                    title={!isAuthenticated ? t('auth.signInRequired') : undefined}
                  >
                    {loadingPlan === plan.key ? '...' : t('pricing.upgrade')}
                  </button>
                ) : (
                  // Paid tier — Stripe price not yet configured
                  <button
                    type="button"
                    disabled
                    className="w-full py-2 text-xs font-semibold text-[var(--fd-text-faint)] border border-border rounded cursor-not-allowed"
                    title={t('pricing.comingSoon')}
                  >
                    {t('pricing.comingSoon')}
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Checkout error */}
      {checkoutError && (
        <p className="mt-4 text-center text-xs text-red-400">{checkoutError}</p>
      )}

      {/* FAQ / notes */}
      <div className="mt-10 space-y-4 text-sm text-[#666]">
        <p>
          <span className="text-[var(--fd-text-dim)] font-semibold">{t('pricing.faqTrialTitle')}</span>
          {' '}{t('pricing.faqTrialBody')}
        </p>
        <p>
          <span className="text-[var(--fd-text-dim)] font-semibold">{t('pricing.faqByokTitle')}</span>
          {' '}{t('pricing.faqByokBody')}
        </p>
        <p>
          <span className="text-[var(--fd-text-dim)] font-semibold">{t('pricing.faqContactTitle')}</span>
          {' '}{t('pricing.faqContactBody')}
        </p>
      </div>
    </div>
  )
}
