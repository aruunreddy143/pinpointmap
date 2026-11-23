import { Link, useParams } from 'react-router-dom'
import { SearchX } from 'lucide-react'
import { PublicPlaceView } from '@/components/PublicPlaceView'
import { Button, EmptyState, InlineError, Skeleton } from '@/components/ui'
import { useAsync } from '@/lib/useAsync'
import { getPublicPlace } from '@/lib/api'

export function ViewerPlacePage() {
  const { id = '' } = useParams()
  const res = useAsync(() => getPublicPlace(id), [id])
  if (res.loading && !res.data) return <div className="flex flex-col gap-3"><Skeleton className="h-40" /><Skeleton className="h-8 w-2/3" /><Skeleton className="h-24" /></div>
  if (res.error) return <InlineError title="Could not load this place" text={res.error} onRetry={res.reload} />
  // A private or unknown place is a 404 for a viewer.
  if (!res.data) return <EmptyState icon={SearchX} title="Place not found" text="It may not exist, or it is not public." action={<Link to="/app"><Button>Back to search</Button></Link>} />
  return <PublicPlaceView place={res.data.place} units={res.data.units} canReport backTo="/app" />
}
