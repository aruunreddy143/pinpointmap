import { Hammer } from 'lucide-react'
import { EmptyState } from '@/components/ui'

export function ComingSoonPage({ title, text }: { title: string; text: string }) {
  return (
    <div className="p-6">
      <EmptyState icon={Hammer} title={title} text={text} />
    </div>
  )
}
