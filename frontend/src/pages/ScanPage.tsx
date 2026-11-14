import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Camera, Check, CircleAlert, ScanLine } from 'lucide-react'
import { Button, Card, Field, cx, inputClass } from '@/components/ui'
import { validate, normalize } from '@/lib/placeId'

// BarcodeDetector is not in every browser's types or runtime.
interface Detector {
  detect(source: CanvasImageSource): Promise<{ rawValue: string }[]>
}
type DetectorCtor = new (opts: { formats: string[] }) => Detector

const REASONS = {
  incomplete: 'Keep typing. The ID has 18 characters after removing dashes.',
  prefix: 'IDs start with PP1 and have exactly 18 characters.',
  characters: 'IDs only use these characters: F C 9 8 J 3 2 7 K 4 5 6 L M P T.',
  checksum: 'The check character does not match. A character is probably mistyped.',
} as const

const getDetector = () => (window as unknown as { BarcodeDetector?: DetectorCtor }).BarcodeDetector

/** Pull an ID out of either a typed ID or a scanned resolver URL (…/p/PP1…). */
function extractId(text: string): string {
  const m = /\/p\/([A-Za-z0-9-]+)/.exec(text)
  return m ? m[1] : text
}

export function ScanPage({ base }: { base: '/staff' | '/app' }) {
  const nav = useNavigate()
  const [text, setText] = useState('')
  const [camera, setCamera] = useState<'off' | 'on' | 'unsupported' | 'denied'>('off')
  const video = useRef<HTMLVideoElement>(null)
  const check = validate(text)
  const touched = text.trim().length > 0

  const open = (id: string) => nav(`/p/${normalize(id)}`)

  useEffect(() => {
    if (camera !== 'on') return
    const Ctor = getDetector()
    if (!Ctor) return
    const detector = new Ctor({ formats: ['qr_code', 'code_128'] })
    let stream: MediaStream | null = null
    let timer = 0
    let stopped = false
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment' } })
      .then((s) => {
        if (stopped) return s.getTracks().forEach((t) => t.stop())
        stream = s
        if (video.current) {
          video.current.srcObject = s
          void video.current.play()
        }
        timer = window.setInterval(async () => {
          if (!video.current) return
          const found = await detector.detect(video.current).catch(() => [])
          const ok = found.map((f) => extractId(f.rawValue)).find((v) => validate(v).ok)
          if (ok) open(ok)
        }, 400)
      })
      .catch(() => setCamera('denied'))
    return () => {
      stopped = true
      window.clearInterval(timer)
      stream?.getTracks().forEach((t) => t.stop())
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [camera])

  return (
    <div className={cx('mx-auto flex max-w-md flex-col gap-5', base === '/staff' && 'p-4 md:p-7')}>
      <div>
        <h1 className="m-0 mb-1 mt-2 text-[22px] font-bold">Scan a place</h1>
        <p className="m-0 text-muted">Scan the QR code on a label, or type the ID.</p>
      </div>
      <Card className="overflow-hidden">
        {camera === 'on' ? (
          <div className="relative aspect-square bg-black">
            <video ref={video} muted playsInline className="size-full object-cover" aria-label="Camera preview" />
            <div className="pointer-events-none absolute inset-8 rounded-2xl border-4 border-accent" />
            <div className="absolute inset-x-0 bottom-3 text-center text-sm font-medium text-white">Point the camera at a PINPOINT QR code</div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 px-6 py-8 text-center">
            <span className="flex size-14 items-center justify-center rounded-full bg-accent-soft text-accent"><ScanLine size={26} aria-hidden /></span>
            <Button variant="primary" icon={Camera} onClick={() => setCamera(getDetector() ? 'on' : 'unsupported')}>Open camera</Button>
            {camera === 'unsupported' && <p role="status" className="m-0 text-[13px] text-muted">This browser can't scan codes. Type the ID below instead.</p>}
            {camera === 'denied' && <p role="status" className="m-0 text-[13px] text-bad">Camera access was blocked. Allow it in your browser settings, or type the ID below.</p>}
          </div>
        )}
      </Card>
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (check.ok) open(check.canonical)
        }}
      >
        <Field label="Or type the ID" htmlFor="manual-id">
          <input id="manual-id" value={text} onChange={(e) => setText(extractId(e.target.value))} placeholder="PP1-FC98J327K4-56LM-T" autoCapitalize="characters" autoComplete="off" spellCheck={false} aria-describedby="id-status" aria-invalid={touched && !check.ok && check.reason !== 'incomplete'} className={cx(inputClass, 'h-[52px] font-mono', touched && (check.ok ? 'border-ok' : check.reason === 'incomplete' ? '' : 'border-bad'))} />
        </Field>
        <div id="id-status" role="status" className={cx('flex items-center gap-2 text-[13px] font-semibold', check.ok ? 'text-ok' : touched && check.reason !== 'incomplete' ? 'text-bad' : 'text-muted')}>
          {touched && (check.ok ? <><Check size={16} aria-hidden />Valid ID. Check character matches.</> : <><CircleAlert size={16} aria-hidden />{REASONS[check.reason]}</>)}
        </div>
        <Button type="submit" variant="primary" size="lg" disabled={!check.ok}>Open place</Button>
      </form>
    </div>
  )
}
