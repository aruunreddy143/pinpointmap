import { Link, Navigate, useParams } from 'react-router-dom'
import { ArrowLeft, Printer } from 'lucide-react'
import { useSession } from '@/app/providers'
import { Barcode, QrCode } from '@/components/codes'
import { useToast } from '@/components/toast'
import { Button, Skeleton } from '@/components/ui'
import { can } from '@/lib/permissions'
import { formatDisplay } from '@/lib/placeId'
import { useAsync } from '@/lib/useAsync'
import { getPlace } from '@/mocks/api'

export function LabelPage() {
  const { id = '' } = useParams()
  const { role } = useSession()
  const toast = useToast()
  const place = useAsync(() => getPlace(id), [id])
  if (role && !can(role, 'place:print')) return <Navigate to={`/staff/places/${id}`} replace />
  const p = place.data

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-5 p-4 md:p-7">
      <div className="flex items-center gap-3 print:hidden">
        <Link to={`/staff/places/${id}`}><Button variant="ghost" icon={ArrowLeft}>Back</Button></Link>
        <div className="flex-1" />
        <Button variant="primary" icon={Printer} onClick={() => { window.print(); toast('Label sent to the printer') }}>Print</Button>
      </div>
      {place.loading || !p || !p.publicId ? (
        <Skeleton className="h-96" />
      ) : (
        <div className="flex flex-col gap-4 rounded-[18px] border-2 border-[#12161c] bg-white p-7 text-[#12161c]">
          <div className="flex items-center justify-between">
            <span className="text-[15px] font-bold tracking-[0.06em]">PINPOINT</span>
            {p.label && <span className="rounded-full border-[1.5px] border-[#12161c] px-2.5 py-0.5 text-xs font-bold">UNIT {p.label}</span>}
          </div>
          <div className="flex items-center gap-5">
            <QrCode publicId={p.publicId} size={176} />
            <div className="min-w-0">
              <div className="text-xl font-bold leading-tight">{p.name}</div>
              <div className="mt-1 text-[13px] text-[#4a5260]">{p.address}<br />{p.locality} {p.postalPin}</div>
              <div className="mt-3 text-xs font-semibold text-[#4a5260]">Scan with any phone camera to open this place.</div>
            </div>
          </div>
          <Barcode publicId={p.publicId} />
          <div className="text-center font-mono text-[17px] font-medium tracking-wider">{formatDisplay(p.publicId)}</div>
        </div>
      )}
      <p className="m-0 text-[13px] text-muted print:hidden">The QR code opens the place's resolver page. It contains the ID only, never coordinates or personal data.</p>
    </div>
  )
}
