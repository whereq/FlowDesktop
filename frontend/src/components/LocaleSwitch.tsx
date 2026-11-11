import { useTranslation } from 'react-i18next'
import Btn from './Btn'
import clsx from 'clsx'

const LANGS = [
  { code: 'en', label: 'EN', title: 'English' },
  { code: 'zh', label: '中', title: '中文' },
] as const

export default function LocaleSwitch() {
  const { i18n } = useTranslation()

  return (
    <div className="flex bg-[var(--fd-bg-elevated)] p-px">
      {LANGS.map(({ code, label, title }) => (
        <Btn
          key={code}
          onClick={() => i18n.changeLanguage(code)}
          title={title}
          variant={i18n.language === code ? 'active' : 'ghost'}
          size="sm"
          className={clsx(
            'locale-btn w-[36px] min-w-[36px]',
            // Override text size for locale labels (smaller than default sm)
            '[&>span]:text-[11px] [&>span]:tracking-widest',
          )}
        >
          <span>{label}</span>
        </Btn>
      ))}
    </div>
  )
}
