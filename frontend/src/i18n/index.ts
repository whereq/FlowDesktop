import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import zh from './locales/zh.json'
import { lsSet, lsGet } from '../utils/storage'

const LOCALE_KEY = 'FlowDesktop_locale'

function getInitialLocale(): string {
  const stored = lsGet(LOCALE_KEY)
  if (stored && ['en', 'zh'].includes(stored)) return stored
  const browser = navigator.language.toLowerCase()
  if (browser.startsWith('zh')) return 'zh'
  return 'en'
}

i18n
  .use(initReactI18next)
  .init({
    resources: { en: { translation: en }, zh: { translation: zh } },
    lng: getInitialLocale(),
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false,
    },
    // Sector/exchange values are data-driven (e.g. raw SEC industry names that the
    // enrichment backfill writes into `stocks.sector`) and may have no translation.
    // Show the raw label instead of leaking the "sectors.X" / "exchanges.X" key.
    parseMissingKeyHandler: (key: string) => {
      const m = /^(?:sectors|exchanges)\.(.+)$/.exec(key)
      return m ? m[1] : key
    },
  })

// Persist locale changes to localStorage
i18n.on('languageChanged', (lng) => {
  lsSet(LOCALE_KEY, lng)
})

export default i18n
