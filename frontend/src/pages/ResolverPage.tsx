import { Link, useParams } from 'react-router-dom'
import { FileQuestion, LockKeyhole, ShieldCheck, TriangleAlert } from 'lucide-react'
import { useSession } from '@/app/providers'
import { Logo } from '@/app/layouts'
import { PublicPlaceView } from '@/components/PublicPlaceView'
import { Button, Card, Skeleton } from '@/components/ui'
import { isStaff } from '@/lib/permissions'
import { useAsync } from '@/lib/useAsync'
import { resolve } from '@/lib/api'

/** The scan target (/p/:id). What it shows depends on who scans (see pinpoint-qr-label skill). */
export function ResolverPage() {
  const { id = '' } = useParams()
  const { role } = useSession()
  const res = useAsync(() => resolve(id), [id, role])
  const r = res.data

  return (
    <div className="mx-auto flex min-h-full max-w-[520px] flex-col gap-5 px-5 pb-8 pt-5">
      <Logo />
      {res.loading && !r ? (
        <Skeleton className="mt-6 h-56" />
      ) : r?.kind === 'invalid' ? (
        <Notice icon={TriangleAlert} tone="warn" title="Check the code" text="This ID does not look right. A character may be mistyped or the code is damaged." />
      ) : r?.kind === 'not_found' ? (
        <Notice icon={FileQuestion} tone="grey" title="No place found" text="The code is valid, but no place is registered with it." />
      ) : r?.kind === 'minimal' ? (
        <>
          <Card className="mt-8 flex flex-col items-center gap-3.5 px-6 py-8 text-center">
            <span className="flex size-16 items-center justify-center rounded-full bg-ok-soft text-ok"><ShieldCheck size={30} aria-hidden /></span>
            <h1 className="m-0 text-[22px] font-bold">Registered PINPOINT place</h1>
            <p className="m-0 leading-relaxed text-muted">This code belongs to a verified place. Its details are private.</p>
          </Card>
          <Card className="flex gap-3 p-5">
            <LockKeyhole size={20} className="mt-0.5 shrink-0 text-accent" aria-hidden />
            <div>
              <div className="mb-0.5 font-bold">Why can't I see the address?</div>
              <div className="text-[13.5px] leading-relaxed text-muted">The owner has not made this place public. Authorised staff can see more.</div>
            </div>
          </Card>
          {!role && <Link to="/"><Button variant="primary" size="lg" className="w-full">Staff sign in</Button></Link>}
        </>
      ) : r?.kind === 'tombstone' ? (
        <>
          <Notice icon={FileQuestion} tone="grey" title={`This place was ${r.status === 'merged' ? 'merged' : r.status === 'split' ? 'split' : 'retired'}`} text="The code is no longer in use for this place." />
          {r.successorIds.map((sid) => <Link key={sid} to={`/p/${sid}`}><Button size="lg" className="w-full">Open the current place</Button></Link>)}
        </>
      ) : r?.kind === 'public' ? (
        <PublicPlaceView place={r.place} units={r.units} canReport={role === 'viewer'} />
      ) : r?.kind === 'staff' && role && isStaff(role) ? (
        <>
          <PublicPlaceView place={r.place} units={r.units} canReport={false} />
          <Link to={`/staff/places/${r.place.id}`}><Button variant="primary" size="lg" className="w-full">Open in staff app</Button></Link>
        </>
      ) : null}
      <p className="m-0 mt-auto text-center text-xs text-muted">PINPOINT · Your data is protected under the DPDP Act, 2023</p>
    </div>
  )
}

function Notice({ icon: Icon, tone, title, text }: { icon: typeof FileQuestion; tone: 'warn' | 'grey'; title: string; text: string }) {
  return (
    <Card className="mt-8 flex flex-col items-center gap-3.5 px-6 py-8 text-center">
      <span className={`flex size-16 items-center justify-center rounded-full ${tone === 'warn' ? 'bg-warn-soft text-warn' : 'bg-grey-soft text-muted'}`}><Icon size={30} aria-hidden /></span>
      <h1 className="m-0 text-[22px] font-bold">{title}</h1>
      <p className="m-0 leading-relaxed text-muted">{text}</p>
    </Card>
  )
}
