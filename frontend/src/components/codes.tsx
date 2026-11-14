import { useEffect, useRef, useState } from 'react'
import QRCode from 'qrcode'
import JsBarcode from 'jsbarcode'
import { Copy } from 'lucide-react'
import { formatDisplay, normalize } from '@/lib/placeId'
import { useToast } from './toast'

const BASE_URL = import.meta.env.VITE_PUBLIC_BASE_URL ?? 'https://pinpoint.example'

export function resolverUrl(publicId: string): string {
  return `${BASE_URL}/p/${normalize(publicId)}`
}

/** QR content is the resolver URL only: no coordinates, no personal data. Error correction Q. */
export function QrCode({ publicId, size = 168 }: { publicId: string; size?: number }) {
  const [svg, setSvg] = useState('')
  useEffect(() => {
    let live = true
    QRCode.toString(resolverUrl(publicId), { type: 'svg', errorCorrectionLevel: 'Q', margin: 0 }).then((s) => {
      if (live) setSvg(s)
    })
    return () => {
      live = false
    }
  }, [publicId])
  return (
    <div
      role="img"
      aria-label={`QR code for ${formatDisplay(publicId)}`}
      style={{ width: size, height: size }}
      className="[&>svg]:size-full"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}

/** Code 128 of the canonical ID (no hyphens), for handheld linear scanners. */
export function Barcode({ publicId, height = 54 }: { publicId: string; height?: number }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    if (ref.current) JsBarcode(ref.current, normalize(publicId), { format: 'CODE128', displayValue: false, height, margin: 0, width: 1.6 })
  }, [publicId, height])
  return <svg ref={ref} role="img" aria-label="Code 128 barcode of the ID" className="w-full" />
}

export function PlaceIdChip({ publicId, tone = 'surface' }: { publicId: string; tone?: 'surface' | 'plain' }) {
  const toast = useToast()
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(formatDisplay(publicId))
      toast('ID copied')
    } catch {
      toast('Could not copy. Select the ID and copy it manually.', 'bad')
    }
  }
  return (
    <div className={tone === 'surface' ? 'flex items-center gap-2 rounded-[10px] border border-border bg-surface-2 py-2 pl-3 pr-1.5' : 'flex items-center gap-2'}>
      <span className="flex-1 truncate font-mono text-[12.5px] tnum">{formatDisplay(publicId)}</span>
      <button type="button" aria-label="Copy ID" onClick={copy} className="flex size-8 items-center justify-center rounded-lg text-muted transition-colors hover:bg-grey-soft hover:text-text">
        <Copy size={16} aria-hidden />
      </button>
    </div>
  )
}
