import { lazy, Suspense, type ComponentProps } from 'react'

// MapLibre is large, so it loads only when a screen with a map is opened.
const Impl = lazy(() => import('./MapView').then((m) => ({ default: m.MapView })))

export function MapView(props: ComponentProps<typeof Impl>) {
  return (
    <Suspense fallback={<div className={`pp-skeleton ${props.className ?? ''}`} role="status" aria-label="Loading map" />}>
      <Impl {...props} />
    </Suspense>
  )
}
