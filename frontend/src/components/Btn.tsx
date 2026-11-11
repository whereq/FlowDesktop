import clsx from 'clsx'
import type { ButtonHTMLAttributes, AnchorHTMLAttributes } from 'react'

/* ─── Button variants ─────────────────────────────────────────────────────── */
type Variant = 'primary' | 'ghost' | 'active' | 'danger'

/* ─── Button sizes ───────────────────────────────────────────────────────── */
type Size = 'sm' | 'md'

interface BtnBaseProps {
  variant?: Variant
  size?: Size
  /** Highlight ghost button with a bright yellow border when active/selected */
  highlight?: boolean
}

type BtnProps = BtnBaseProps &
  (ButtonHTMLAttributes<HTMLButtonElement> | AnchorHTMLAttributes<HTMLAnchorElement>)

/**
 * FlowDesktop shared button component — Metro flat design.
 *
 * Variants:
 *   primary  — Metro blue solid.    Primary actions: Add, Save, Add Defaults.
 *   ghost    — Transparent + border. Secondary / inactive nav / neutral actions.
 *   active   — Metro blue solid.   Active nav link (stays blue when selected).
 *   danger   — Red border.         Destructive / remove actions.
 *
 * Sizes:
 *   sm — 30px height, 12px horizontal padding.  Nav, toggles, small actions.
 *   md — 36px height, 16px horizontal padding.  Default, primary actions.
 */
export default function Btn({
  variant = 'ghost',
  size = 'md',
  highlight = false,
  className,
  children,
  ...props
}: BtnProps) {
  const variantClass = {
    primary: [
      'bg-[var(--color-accent)]', 'hover:bg-[var(--color-accent)]', 'text-white',
      'border border-[var(--color-accent)]',
    ],
    ghost: [
      'bg-[var(--fd-bg-elevated)]', 'text-[var(--fd-text-secondary)]',
      'border border-[var(--fd-rule-strong)]',
      'hover:bg-[var(--fd-bg-hover)]', 'hover:text-[var(--fd-text-primary)]', 'hover:border-[var(--color-accent)]',
    ],
    active: [
      'bg-[var(--color-accent)]', 'text-white',
      'border border-[var(--color-accent)]',
    ],
    danger: [
      'bg-transparent', 'text-[var(--fd-text-dim)]',
      'border border-border',
      'hover:border-[var(--color-stock-down)]', 'hover:text-[var(--color-stock-down)]',
    ],
  }[variant]

  const sizeClass = {
    sm: 'h-[30px] px-3 text-xs font-semibold',
    md: 'h-9 px-4 text-sm font-semibold',
  }[size]

  const isButton = 'onClick' in props || !('href' in props)

  const baseClass = [
    ...variantClass,
    sizeClass,
    'inline-flex items-center justify-center gap-2',
    'transition-colors duration-150 cursor-pointer select-none',
    highlight && variant === 'ghost' ? 'border-2 border-[var(--color-accent)] shadow-[0_0_6px_var(--color-accent)]' : '',
    className as string,
  ]

  if (isButton) {
    const buttonProps = { ...props } as ButtonHTMLAttributes<HTMLButtonElement>
    delete (buttonProps as Record<string, unknown>).className
    return (
      <button
        {...buttonProps}
        className={clsx(baseClass)}
      >
        {children}
      </button>
    )
  }

  const anchorProps = { ...props } as AnchorHTMLAttributes<HTMLAnchorElement>
  delete (anchorProps as Record<string, unknown>).className
  return (
    <a
      {...anchorProps}
      className={clsx(baseClass, 'no-underline')}
    >
      {children}
    </a>
  )
}
