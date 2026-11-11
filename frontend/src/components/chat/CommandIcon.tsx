import type { SVGProps } from 'react'

export function CommandIcon({ id, size = 13 }: { id: string; size?: number }) {
  const p: SVGProps<SVGSVGElement> = {
    width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
    stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'square', strokeLinejoin: 'miter',
  }
  switch (id) {
    case 'analyze':
      return <svg {...p}><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
    case 'committee':
      return <svg {...p}><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
    case 'compare':
      return <svg {...p}><path d="M8 3L4 7l4 4M4 7h16M16 21l4-4-4-4M20 17H4"/></svg>
    case 'strategy':
      return <svg {...p}><polyline points="4 17 9 12 13 16 20 9"/></svg>
    case 'screen':
      return <svg {...p}><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    case 'macro':
      return <svg {...p}><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 010 20"/></svg>
    case 'portfolio':
      return <svg {...p}><rect x="2" y="7" width="20" height="15"/><path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/></svg>
    default:
      return null
  }
}
