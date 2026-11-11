import FDLogo from './ui/FDLogo'

interface FlowDesktopLogoProps {
  className?: string
  size?: number
}

/**
 * FlowDesktop brand logo — K-Chart F mark with candlestick motif.
 * Backward-compatible wrapper around the new FDLogo component.
 */
export default function FlowDesktopLogo({ className = 'w-8 h-8', size }: FlowDesktopLogoProps) {
  return <FDLogo size={size ?? 28} showWord={false} className={className} />
}
