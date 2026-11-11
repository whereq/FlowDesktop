import { useEffect, type ReactNode } from 'react'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: ReactNode
  actions: ReactNode
}

export default function Modal({ isOpen, onClose, title, children, actions }: ModalProps) {
  useEffect(() => {
    if (!isOpen) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/60" onClick={onClose} />
      {/* Dialog */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-6 pointer-events-none">
        <div
          className="bg-surface-card border border-border w-full max-w-sm pointer-events-auto"
          style={{ boxShadow: '0 8px 40px rgba(0,0,0,0.7)' }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <span className="text-xs font-bold tracking-widest uppercase text-[var(--fd-text-primary)]">{title}</span>
            <button
              onClick={onClose}
              aria-label="Close"
              className="flex items-center justify-center w-6 h-6 text-[var(--fd-text-dim)] hover:text-[var(--fd-text-secondary)] transition-colors"
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
                <path d="M1 1l8 8M9 1l-8 8" />
              </svg>
            </button>
          </div>
          {/* Body */}
          <div className="px-4 py-4">
            {children}
          </div>
          {/* Footer */}
          <div className="px-4 py-3 border-t border-border flex justify-end gap-2">
            {actions}
          </div>
        </div>
      </div>
    </>
  )
}
