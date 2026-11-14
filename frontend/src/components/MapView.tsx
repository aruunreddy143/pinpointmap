import { useEffect, useRef } from 'react'
import * as maplibregl from 'maplibre-gl'
import type { StyleSpecification } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

// Bundlers need to be told where the worker file lives, or the map never renders.
maplibregl.setWorkerUrl(workerUrl)
import 'maplibre-gl/dist/maplibre-gl.css'
import type { LatLon, PlaceStatus } from '@/lib/types'

export interface MapMarker {
  id: string
  geo: LatLon
  status: PlaceStatus
  label?: string
}

interface Props {
  markers?: MapMarker[]
  selectedId?: string | null
  onSelect?: (id: string) => void
  center: LatLon
  zoom?: number
  /** A draggable registration pin. Click on the map also moves it. */
  pin?: { geo: LatLon; onMove: (g: LatLon) => void }
  className?: string
  ariaLabel: string
  /** Pixels covered on the right by an overlay panel, so the centred place stays visible. */
  padRight?: number
}

// Tile source is configurable (VITE_MAP_STYLE_URL). The fallback is OpenStreetMap raster tiles for development only.
const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
}

const DOT: Record<PlaceStatus, string> = {
  active: 'var(--ok)',
  pending_verification: 'var(--warn)',
  draft: 'var(--muted)',
  rejected: 'var(--bad)',
  retired: 'var(--muted)',
  merged: 'var(--muted)',
  split: 'var(--muted)',
}

function dotEl(color: string, selected: boolean): HTMLButtonElement {
  const el = document.createElement('button')
  el.type = 'button'
  const s = selected ? 26 : 16
  el.style.cssText = `width:${s}px;height:${s}px;border-radius:999px;background:${color};border:3px solid var(--surface);box-shadow:0 1px 4px rgba(0,0,0,.35);cursor:pointer;padding:0;${selected ? 'outline:3px solid var(--accent);' : ''}`
  return el
}

export function MapView({ markers = [], selectedId, onSelect, center, zoom = 15, pin, className, ariaLabel, padRight = 0 }: Props) {
  const host = useRef<HTMLDivElement>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const markerRefs = useRef<maplibregl.Marker[]>([])
  const pinRef = useRef<maplibregl.Marker | null>(null)
  const pinMove = useRef(pin?.onMove)
  const onPinMove = pin?.onMove
  useEffect(() => {
    pinMove.current = onPinMove
  })

  useEffect(() => {
    if (!host.current) return
    const styleUrl = import.meta.env.VITE_MAP_STYLE_URL as string | undefined
    const m = new maplibregl.Map({
      container: host.current,
      style: styleUrl || FALLBACK_STYLE,
      center: [center.lon, center.lat], // MapLibre is (lon, lat)
      zoom,
      attributionControl: { compact: true },
    })
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-left')
    m.on('click', (e) => {
      if (pinMove.current) pinMove.current({ lat: e.lngLat.lat, lon: e.lngLat.lng })
    })
    map.current = m
    // Keep the canvas in sync with layout changes (sidebars, window resize, mobile stacking).
    const ro = new ResizeObserver(() => m.resize())
    ro.observe(host.current)
    return () => {
      ro.disconnect()
      m.remove()
      map.current = null
    }
    // The map is created once; position changes are applied by the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const m = map.current
    if (!m) return
    markerRefs.current.forEach((x) => x.remove())
    markerRefs.current = markers.map((mk) => {
      const el = dotEl(DOT[mk.status], mk.id === selectedId)
      el.setAttribute('aria-label', mk.label ?? 'Place')
      el.addEventListener('click', (ev) => {
        ev.stopPropagation()
        onSelect?.(mk.id)
      })
      return new maplibregl.Marker({ element: el }).setLngLat([mk.geo.lon, mk.geo.lat]).addTo(m)
    })
  }, [markers, selectedId, onSelect])

  useEffect(() => {
    const m = map.current
    if (!m || !pin) return
    if (!pinRef.current) {
      const marker = new maplibregl.Marker({ draggable: true, color: '#2457E6' }).setLngLat([pin.geo.lon, pin.geo.lat]).addTo(m)
      marker.on('dragend', () => {
        const p = marker.getLngLat()
        pinMove.current?.({ lat: p.lat, lon: p.lng })
      })
      pinRef.current = marker
    } else {
      pinRef.current.setLngLat([pin.geo.lon, pin.geo.lat])
    }
  }, [pin])

  useEffect(() => {
    map.current?.easeTo({ center: [center.lon, center.lat], padding: { right: padRight, top: 0, bottom: 0, left: 0 }, duration: 400 })
  }, [center.lat, center.lon, padRight])

  // MapLibre's own CSS sets `position: relative` on its container (unlayered, so it beats Tailwind
  // utilities). The outer div carries the layout classes; the inner one just fills it.
  return (
    <div role="region" aria-label={ariaLabel} className={`pp-map ${className ?? ''}`}>
      <div ref={host} style={{ width: '100%', height: '100%' }} />
    </div>
  )
}
