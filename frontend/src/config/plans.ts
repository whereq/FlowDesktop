/**
 * FlowDesktop subscription plan definitions.
 *
 * stripeProductId  — Stripe Product ID (prod_xxx). Set. Used for reference.
 * stripePriceId    — Stripe Price ID (price_xxx). Set this once you create a
 *                    recurring Price under each Product in the Stripe Dashboard.
 *                    Leaving it null keeps the upgrade button in "Coming soon" state.
 * keycloakRole     — Realm role assigned to the user after successful payment.
 */
export interface PlanConfig {
  key: string
  keycloakRole: string
  stripeProductId: string
  stripePriceId: string | null   // null = not yet configured → button disabled
  highlight: boolean
  price: string
  pricePeriod: string
  msgLimit: string
  msgLimitKey?: string           // if set, used as a direct i18n key instead of the default template
  featureKeys: string[]
}

export const PAID_PLANS: PlanConfig[] = [
  {
    key: 'byok',
    keycloakRole: 'fd-tier-byok',
    stripeProductId: '',          // to be created in Stripe dashboard
    stripePriceId: null,          // not yet configured
    highlight: false,
    price: '$9.99',
    pricePeriod: '/ mo',
    msgLimit: '',
    msgLimitKey: 'pricing.msgLimitByok',
    featureKeys: ['byok_f1', 'byok_f2', 'byok_f3', 'byok_f4'],
  },
  {
    key: 'basic',
    keycloakRole: 'fd-tier-1',
    stripeProductId: 'prod_EXAMPLE',
    stripePriceId: 'price_EXAMPLE',
    highlight: false,
    price: '$19.99',
    pricePeriod: '/ mo',
    msgLimit: '200',
    featureKeys: ['basic_f1', 'basic_f2', 'basic_f3', 'basic_f4'],
  },
  {
    key: 'pro',
    keycloakRole: 'fd-tier-2',
    stripeProductId: 'prod_EXAMPLE',
    stripePriceId: 'price_EXAMPLE',
    highlight: true,
    price: '$59.99',
    pricePeriod: '/ mo',
    msgLimit: '1000',
    featureKeys: ['pro_f1', 'pro_f2', 'pro_f3', 'pro_f4', 'pro_f5'],
  },
  {
    key: 'unlimited',
    keycloakRole: 'fd-tier-unlimited',
    stripeProductId: 'prod_EXAMPLE',
    stripePriceId: 'price_EXAMPLE',
    highlight: false,
    price: '$99.99',
    pricePeriod: '/ mo',
    msgLimit: '∞',
    featureKeys: ['unlimited_f1', 'unlimited_f2', 'unlimited_f3', 'unlimited_f4'],
  },
]
