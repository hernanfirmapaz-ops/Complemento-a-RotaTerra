import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

interface Props {
  isOpen: boolean
  initialCenter?: [number, number] // [lon, lat]
  onClose: () => void
  onConfirmPolygon: (name: string, geojsonFile: File) => Promise<void>
}

interface PresetLocation {
  label: string
  region: string
  lon: number
  lat: number
  zoom: number
}

const AGRO_ZONES: PresetLocation[] = [
  {
    label: 'El Trapiche / Piedemonte',
    region: 'San Luis',
    lon: -66.085,
    lat: -33.128,
    zoom: 14,
  },
  {
    label: 'Villa Mercedes',
    region: 'San Luis',
    lon: -65.46,
    lat: -33.67,
    zoom: 13,
  },
  {
    label: 'Río Cuarto',
    region: 'Córdoba',
    lon: -64.35,
    lat: -33.13,
    zoom: 13,
  },
  {
    label: 'Marcos Juárez',
    region: 'Córdoba',
    lon: -62.1,
    lat: -32.7,
    zoom: 13,
  },
  {
    label: 'Pergamino',
    region: 'Buenos Aires',
    lon: -60.57,
    lat: -33.89,
    zoom: 13,
  },
  {
    label: 'Tandil / Balcarce',
    region: 'Buenos Aires',
    lon: -58.95,
    lat: -37.55,
    zoom: 13,
  },
  {
    label: 'Venado Tuerto',
    region: 'Santa Fe',
    lon: -61.97,
    lat: -33.75,
    zoom: 13,
  },
  {
    label: 'Paraná / Diamante',
    region: 'Entre Ríos',
    lon: -60.45,
    lat: -31.85,
    zoom: 13,
  },
]

/** Calcula el área aproximada en hectáreas de un polígono [lon, lat][] usando proyección equirectangular local. */
function computePolygonAreaHa(pts: [number, number][]): number {
  if (pts.length < 3) return 0
  const latMeanRad =
    (pts.reduce((acc, p) => acc + p[1], 0) / pts.length) * (Math.PI / 180)
  const metersPerDegLat = 111132.954
  const metersPerDegLon = 111319.488 * Math.cos(latMeanRad)

  const x0 = pts[0][0]
  const y0 = pts[0][1]
  let twiceAreaM2 = 0
  for (let i = 0; i < pts.length; i++) {
    const p1 = pts[i]
    const p2 = pts[(i + 1) % pts.length]
    const x1 = (p1[0] - x0) * metersPerDegLon
    const y1 = (p1[1] - y0) * metersPerDegLat
    const x2 = (p2[0] - x0) * metersPerDegLon
    const y2 = (p2[1] - y0) * metersPerDegLat
    twiceAreaM2 += x1 * y2 - x2 * y1
  }
  return Math.abs(twiceAreaM2) * 0.5 / 10000
}

/** Calcula el perímetro aproximado en metros de un polígono [lon, lat][]. */
function computePerimeterM(pts: [number, number][]): number {
  if (pts.length < 2) return 0
  const latMeanRad =
    (pts.reduce((acc, p) => acc + p[1], 0) / pts.length) * (Math.PI / 180)
  const metersPerDegLat = 111132.954
  const metersPerDegLon = 111319.488 * Math.cos(latMeanRad)
  let total = 0
  for (let i = 0; i < pts.length; i++) {
    const p1 = pts[i]
    const p2 = pts[(i + 1) % pts.length]
    const dx = (p2[0] - p1[0]) * metersPerDegLon
    const dy = (p2[1] - p1[1]) * metersPerDegLat
    total += Math.hypot(dx, dy)
  }
  return total
}

export function PolygonMapDrawer({
  isOpen,
  initialCenter,
  onClose,
  onConfirmPolygon,
}: Props) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<maplibregl.Marker[]>([])

  const [drawTool, setDrawTool] = useState<'polygon' | 'rectangle'>('polygon')
  const [vertices, setVertices] = useState<[number, number][]>([])
  const [rectFirstCorner, setRectFirstCorner] = useState<[number, number] | null>(
    null,
  )
  const [lotName, setLotName] = useState<string>('Mi Lote Agrícola')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [searchStatus, setSearchStatus] = useState<string | null>(null)
  const [basemapStyle, setBasemapStyle] = useState<'satellite' | 'streets'>(
    'satellite',
  )
  const [submitting, setSubmitting] = useState<boolean>(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const verticesRef = useRef(vertices)
  verticesRef.current = vertices
  const drawToolRef = useRef(drawTool)
  drawToolRef.current = drawTool
  const rectCornerRef = useRef(rectFirstCorner)
  rectCornerRef.current = rectFirstCorner

  const areaHa = computePolygonAreaHa(vertices)
  const perimeterM = computePerimeterM(vertices)

  // Inicializar el mapa interactivo cuando se abre el selector
  useEffect(() => {
    if (!isOpen || !mapContainerRef.current) return

    const center: [number, number] = initialCenter ?? [-66.085, -33.128]

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          satellite: {
            type: 'raster',
            tiles: [
              'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            ],
            tileSize: 256,
            attribution: 'Esri World Imagery',
          },
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap',
          },
        },
        layers: [
          {
            id: 'osm-layer',
            type: 'raster',
            source: 'osm',
            layout: {
              visibility: 'visible',
            },
          },
          {
            id: 'sat-layer',
            type: 'raster',
            source: 'satellite',
            layout: {
              visibility: 'visible',
            },
          },
        ],
      },
      center,
      zoom: 14,
      pitch: 0,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    mapRef.current = map

    map.on('load', () => {
      map.addSource('drawn-polygon', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [],
        },
      })

      // Relleno semitransparente del polígono
      map.addLayer({
        id: 'drawn-polygon-fill',
        type: 'fill',
        source: 'drawn-polygon',
        filter: ['==', '$type', 'Polygon'],
        paint: {
          'fill-color': '#10b981',
          'fill-opacity': 0.28,
        },
      })

      // Borde amarillo brillante del polígono o línea en construcción
      map.addLayer({
        id: 'drawn-polygon-line',
        type: 'line',
        source: 'drawn-polygon',
        paint: {
          'line-color': '#facc15',
          'line-width': 3.5,
        },
      })
    })

    map.on('click', (e) => {
      const clicked: [number, number] = [
        Number(e.lngLat.lng.toFixed(6)),
        Number(e.lngLat.lat.toFixed(6)),
      ]

      if (drawToolRef.current === 'rectangle') {
        const first = rectCornerRef.current
        if (!first) {
          setRectFirstCorner(clicked)
          setVertices([clicked])
        } else {
          const minLon = Math.min(first[0], clicked[0])
          const maxLon = Math.max(first[0], clicked[0])
          const minLat = Math.min(first[1], clicked[1])
          const maxLat = Math.max(first[1], clicked[1])
          setVertices([
            [minLon, maxLat],
            [maxLon, maxLat],
            [maxLon, minLat],
            [minLon, minLat],
          ])
          setRectFirstCorner(null)
        }
      } else {
        setVertices((prev) => [...prev, clicked])
      }
    })

    return () => {
      markersRef.current.forEach((m) => m.remove())
      markersRef.current = []
      map.remove()
      mapRef.current = null
    }
  }, [isOpen])

  // Alternar vista Satélite / Calles
  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) return
    if (map.getLayer('sat-layer')) {
      map.setLayoutProperty(
        'sat-layer',
        'visibility',
        basemapStyle === 'satellite' ? 'visible' : 'none',
      )
    }
  }, [basemapStyle])

  // Actualizar el polígono GeoJSON y los marcadores arrastrables de cada esquina
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const updateGeoJsonSource = () => {
      const src = map.getSource('drawn-polygon') as
        | maplibregl.GeoJSONSource
        | undefined
      if (!src) return

      const features: GeoJSON.Feature[] = []
      if (vertices.length >= 3) {
        const ring = [...vertices, vertices[0]]
        features.push({
          type: 'Feature',
          properties: {},
          geometry: {
            type: 'Polygon',
            coordinates: [ring],
          },
        })
      } else if (vertices.length === 2) {
        features.push({
          type: 'Feature',
          properties: {},
          geometry: {
            type: 'LineString',
            coordinates: vertices,
          },
        })
      }
      src.setData({
        type: 'FeatureCollection',
        features,
      })
    }

    if (map.isStyleLoaded()) {
      updateGeoJsonSource()
    } else {
      map.once('load', updateGeoJsonSource)
    }

    // Recrear marcadores arrastrables para cada vértice del lote
    markersRef.current.forEach((m) => m.remove())
    markersRef.current = []

    vertices.forEach((pt, idx) => {
      const el = document.createElement('div')
      el.className = 'polygon-vertex-marker'
      el.innerText = String(idx + 1)
      el.title = `Esquina #${idx + 1} (arrastrá para mover)`

      const marker = new maplibregl.Marker({
        element: el,
        draggable: true,
      })
        .setLngLat(pt)
        .addTo(map)

      marker.on('dragend', () => {
        const lngLat = marker.getLngLat()
        const updated: [number, number] = [
          Number(lngLat.lng.toFixed(6)),
          Number(lngLat.lat.toFixed(6)),
        ]
        setVertices((prev) =>
          prev.map((item, i) => (i === idx ? updated : item)),
        )
      })

      markersRef.current.push(marker)
    })
  }, [vertices])

  if (!isOpen) return null

  const flyToLocation = (lon: number, lat: number, zoom = 14) => {
    const map = mapRef.current
    if (!map) return
    map.flyTo({ center: [lon, lat], zoom, duration: 900 })
  }

  const handleSearchLocation = async (e: React.FormEvent) => {
    e.preventDefault()
    const q = searchQuery.trim()
    if (!q) return
    setSearchStatus('Buscando ubicación...')

    // 1. Verificar si ingresó coordenadas directas "lat, lon"
    const coordMatch = q.match(
      /^(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)$/,
    )
    if (coordMatch) {
      const a = Number(coordMatch[1])
      const b = Number(coordMatch[2])
      // En Argentina latitud ~ -20 a -55, longitud ~ -53 a -74
      const [lat, lon] = Math.abs(a) < 56 && Math.abs(b) > 52 ? [a, b] : [b, a]
      flyToLocation(lon, lat, 14)
      setSearchStatus(`Coordenadas centradas (${lat.toFixed(4)}, ${lon.toFixed(4)})`)
      return
    }

    // 2. Buscar coincidencia rápida en zonas agrícolas predefinidas
    const localMatch = AGRO_ZONES.find(
      (z) =>
        z.label.toLowerCase().includes(q.toLowerCase()) ||
        z.region.toLowerCase().includes(q.toLowerCase()),
    )
    if (localMatch) {
      flyToLocation(localMatch.lon, localMatch.lat, localMatch.zoom)
      setSearchStatus(`Centrado en ${localMatch.label} (${localMatch.region})`)
      return
    }

    // 3. Geocodificación Nominatim OpenStreetMap
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
          q + ', Argentina',
        )}&limit=1`,
      )
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data) && data.length > 0) {
          const lon = Number(data[0].lon)
          const lat = Number(data[0].lat)
          flyToLocation(lon, lat, 14)
          setSearchStatus(`Ubicación encontrada: ${data[0].display_name}`)
          return
        }
      }
      setSearchStatus(
        'No se encontró esa localidad. Probá con otra ciudad o ingresá coordenadas (ej: -33.12, -66.08).',
      )
    } catch {
      setSearchStatus(
        'Búsqueda externa no disponible. Elegí una zona rápida abajo o escribí coordenadas (ej: -33.12, -66.08).',
      )
    }
  }

  /** Crea un polígono de ejemplo de ~160 ha centrado en la vista actual del mapa con 1 clic. */
  const handleStampPolygonAtCenter = () => {
    const map = mapRef.current
    if (!map) return
    const c = map.getCenter()
    const dLon = 0.0072
    const dLat = 0.0058
    setVertices([
      [Number((c.lng - dLon).toFixed(6)), Number((c.lat + dLat).toFixed(6))],
      [Number((c.lng + dLon).toFixed(6)), Number((c.lat + dLat * 0.85).toFixed(6))],
      [Number((c.lng + dLon * 0.92).toFixed(6)), Number((c.lat - dLat).toFixed(6))],
      [Number((c.lng - dLon * 0.88).toFixed(6)), Number((c.lat - dLat * 0.9).toFixed(6))],
    ])
    setRectFirstCorner(null)
  }

  const handleConfirm = async () => {
    if (vertices.length < 3) {
      setSubmitError('Marcá al menos 3 esquinas en el mapa para cerrar el lote.')
      return
    }
    if (areaHa < 0.5) {
      setSubmitError('El polígono dibujado es demasiado pequeño (< 0.5 ha).')
      return
    }
    if (areaHa > 6500) {
      setSubmitError(
        `El lote dibujado tiene ${areaHa.toFixed(0)} ha. Para obtener una maqueta 3D detallada a 30 m se recomienda dibujar lotes o sectores de hasta 6.500 ha.`,
      )
      return
    }

    setSubmitting(true)
    setSubmitError(null)
    try {
      const cleanName = lotName.trim() || 'Mi Lote Dibujado'
      const ring = [...vertices, vertices[0]]
      const featureCollection = {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            properties: {
              name: cleanName,
              source: 'drawn_by_agronomist',
            },
            geometry: {
              type: 'Polygon',
              coordinates: [ring],
            },
          },
        ],
      }
      const blob = new Blob([JSON.stringify(featureCollection, null, 2)], {
        type: 'application/geo+json',
      })
      const safeFileName =
        cleanName
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '_')
          .replace(/^_|_$/g, '') || 'lote_dibujado'
      const file = new File([blob], `${safeFileName}.geojson`, {
        type: 'application/geo+json',
      })
      await onConfirmPolygon(cleanName, file)
    } catch (err) {
      setSubmitError((err as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="drawer-modal-backdrop">
      <div className="drawer-modal-card">
        {/* Encabezado del dibujador de polígonos */}
        <div className="drawer-modal-header">
          <div>
            <span className="drawer-step-badge">
              PASO 1 · UBICÁ Y DELIMITÁ TU CAMPO CON POLÍGONOS
            </span>
            <h2>✏️ Seleccioná dónde está tu terreno en el mapa</h2>
            <p>
              Hacé clic en el mapa para marcar cada esquina de tu lote (o
              arrastrá los puntos numerados para ajustar el alambre).
            </p>
          </div>
          <button
            type="button"
            className="drawer-close-btn"
            onClick={onClose}
            disabled={submitting}
          >
            ✕ Cerrar
          </button>
        </div>

        {/* Barra de búsqueda de localidad / coordenadas + saltos rápidos */}
        <div className="drawer-search-bar">
          <form onSubmit={handleSearchLocation} className="drawer-search-form">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="🔍 Buscar localidad, provincia o coordenadas GPS (ej: Río Cuarto, Pergamino o -33.12, -66.08)..."
              className="drawer-search-input"
            />
            <button type="submit" className="drawer-search-btn">
              Ir a zona
            </button>
          </form>

          <div className="drawer-quick-zones">
            <span className="drawer-quick-label">Zonas rápidas:</span>
            {AGRO_ZONES.map((z) => (
              <button
                key={z.label}
                type="button"
                className="drawer-zone-chip"
                onClick={() => {
                  flyToLocation(z.lon, z.lat, z.zoom)
                  setSearchStatus(`Centrado en ${z.label} (${z.region})`)
                }}
              >
                📍 {z.label}
              </button>
            ))}
          </div>
          {searchStatus && (
            <div className="drawer-search-status">{searchStatus}</div>
          )}
        </div>

        {/* Cuerpo central: Mapa a la izquierda + Controles intuitivos del polígono a la derecha */}
        <div className="drawer-body-grid">
          <div className="drawer-map-wrapper">
            <div ref={mapContainerRef} className="drawer-map-canvas" />

            {/* Barra flotante superior dentro del mapa */}
            <div className="drawer-map-floating-tools">
              <button
                type="button"
                className={`drawer-tool-pill ${
                  drawTool === 'polygon' ? 'active' : ''
                }`}
                onClick={() => {
                  setDrawTool('polygon')
                  setRectFirstCorner(null)
                }}
              >
                ✏️ Polígono libre (clic por esquina)
              </button>
              <button
                type="button"
                className={`drawer-tool-pill ${
                  drawTool === 'rectangle' ? 'active' : ''
                }`}
                onClick={() => {
                  setDrawTool('rectangle')
                  setRectFirstCorner(null)
                  setVertices([])
                }}
              >
                ⬛ Lote rectangular (2 clics)
              </button>
              <button
                type="button"
                className="drawer-tool-pill"
                onClick={handleStampPolygonAtCenter}
                title="Crea un polígono de 4 esquinas en el centro del mapa para que lo ajustes arrastrando los vértices"
              >
                🎯 Marcar lote aquí y ajustar
              </button>
              <button
                type="button"
                className="drawer-tool-pill"
                onClick={() =>
                  setBasemapStyle((b) =>
                    b === 'satellite' ? 'streets' : 'satellite',
                  )
                }
              >
                {basemapStyle === 'satellite'
                  ? '🗺️ Ver Mapa / Rutas'
                  : '🛰️ Ver Satélite'}
              </button>
            </div>

            {/* Instrucción flotante inferior */}
            <div className="drawer-map-bottom-hint">
              {drawTool === 'rectangle'
                ? rectFirstCorner
                  ? '👉 Hacé clic en la esquina opuesta para completar el rectángulo del lote'
                  : '👉 Hacé clic en la primera esquina de tu lote rectangular'
                : vertices.length === 0
                  ? '👉 Hacé clic sobre el mapa satelital para marcar la Esquina 1 de tu lote'
                  : vertices.length < 3
                    ? `👉 Tenés ${vertices.length} punto(s). Marcá al menos 3 esquinas para cerrar el polígono del lote`
                    : `✅ Polígono de ${vertices.length} esquinas listo (${areaHa.toFixed(1)} ha). Podés seguir agregando puntos o arrastrar los números para corregir.`}
            </div>
          </div>

          {/* Panel lateral derecho del dibujador */}
          <div className="drawer-side-panel">
            <div className="drawer-side-box">
              <label className="drawer-field-label">
                Nombre del campo o potrero
              </label>
              <input
                type="text"
                value={lotName}
                onChange={(e) => setLotName(e.target.value)}
                placeholder="Ej: Establecimiento Don Pedro - Lote 4"
                className="drawer-name-input"
              />
            </div>

            <div className="drawer-stats-grid">
              <div className="drawer-stat-card">
                <span>Superficie calculada</span>
                <strong
                  className={
                    areaHa >= 1 && areaHa <= 5000 ? 'text-emerald' : ''
                  }
                >
                  {areaHa > 0 ? `${areaHa.toFixed(1)} ha` : '0 ha'}
                </strong>
                <small>
                  {areaHa > 0
                    ? `${(areaHa / 100).toFixed(2)} km²`
                    : 'Marcá 3+ esquinas'}
                </small>
              </div>
              <div className="drawer-stat-card">
                <span>Esquinas / Alambre</span>
                <strong>{vertices.length} puntos</strong>
                <small>
                  {perimeterM > 0
                    ? `Perímetro: ${(perimeterM / 1000).toFixed(2)} km`
                    : 'Sin perímetro'}
                </small>
              </div>
            </div>

            <div className="drawer-edit-actions">
              <button
                type="button"
                className="drawer-secondary-btn"
                onClick={() => setVertices((prev) => prev.slice(0, -1))}
                disabled={vertices.length === 0 || submitting}
              >
                ↩️ Deshacer último punto
              </button>
              <button
                type="button"
                className="drawer-secondary-btn"
                onClick={() => {
                  setVertices([])
                  setRectFirstCorner(null)
                }}
                disabled={vertices.length === 0 || submitting}
              >
                🗑️ Borrar todo
              </button>
            </div>

            {vertices.length > 0 && (
              <div className="drawer-coords-list">
                <div className="drawer-coords-title">
                  Coordenadas de las esquinas (WGS84):
                </div>
                <div className="drawer-coords-scroll">
                  {vertices.map((pt, i) => (
                    <div key={i} className="drawer-coord-row">
                      <span className="drawer-coord-badge">#{i + 1}</span>
                      <span>
                        Lat {pt[1].toFixed(5)}° · Lon {pt[0].toFixed(5)}°
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {submitError && (
              <div className="drawer-error-banner">⚠️ {submitError}</div>
            )}

            <div className="drawer-confirm-box">
              <button
                type="button"
                className="drawer-confirm-btn"
                disabled={vertices.length < 3 || submitting}
                onClick={handleConfirm}
              >
                {submitting
                  ? '⏳ Descargando relieve 3D y simulando lluvia...'
                  : '🚀 Confirmar Polígono y Ver Maqueta 3D'}
              </button>
              <small className="drawer-confirm-note">
                Al confirmar, el sistema descarga automáticamente las alturas
                reales del satélite Copernicus (30 m), arma la maqueta 3D y
                simula cómo escurre la lluvia en tu lote.
              </small>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
