import { useEffect, useRef } from 'react'
import maplibregl, {
  type CustomLayerInterface,
  MercatorCoordinate,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import * as THREE from 'three'
import type { FieldOut, MeshOut, PointOut } from '../types/api'

export type InteractionMode = 'inspect' | 'profile'
export type BasemapMode = 'satellite' | 'osm'

export interface LayerVisibility {
  basemap: BasemapMode
  mesh3d: boolean
  wireframe: boolean
  boundary: boolean
}

interface Props {
  field: FieldOut | null
  mesh: MeshOut | null
  viewMode: '2d' | '3d'
  exaggeration: number
  layers: LayerVisibility
  interactionMode: InteractionMode
  profileDraft: [number, number][]
  selectedPoint: PointOut | null
  onMapClick: (lon: number, lat: number) => void
  onCursorMove: (lon: number, lat: number) => void
}

/** Gradiente hipsométrico sobrio (verde bajo -> ocre medio -> marrón/blanco alto). */
function hypsometricColor(t: number, inField: boolean): [number, number, number] {
  const u = Math.min(1, Math.max(0, t))
  let r = 0
  let g = 0
  let b = 0
  if (u < 0.35) {
    const k = u / 0.35
    r = 0.20 + 0.30 * k
    g = 0.48 + 0.24 * k
    b = 0.28 - 0.06 * k
  } else if (u < 0.75) {
    const k = (u - 0.35) / 0.40
    r = 0.50 + 0.34 * k
    g = 0.72 - 0.10 * k
    b = 0.22 + 0.06 * k
  } else {
    const k = (u - 0.75) / 0.25
    r = 0.84 + 0.10 * k
    g = 0.62 + 0.24 * k
    b = 0.28 + 0.45 * k
  }
  if (!inField) {
    // Zona de aporte externa ligeramente atenuada para distinguir el interior del lote
    const gray = 0.3 * r + 0.59 * g + 0.11 * b
    r = 0.55 * r + 0.45 * gray
    g = 0.55 * g + 0.45 * gray
    b = 0.55 * b + 0.45 * gray
  }
  return [r, g, b]
}

interface ThreeLayerController extends CustomLayerInterface {
  rebuild: (
    meshData: MeshOut | null,
    exaggeration: number,
    vis: LayerVisibility,
  ) => void
  disposeAll: () => void
}

function createTerrainCustomLayer(
  getMap: () => maplibregl.Map | null,
): ThreeLayerController {
  const camera = new THREE.Camera()
  const scene = new THREE.Scene()

  const ambient = new THREE.AmbientLight(0xffffff, 0.75)
  const sun = new THREE.DirectionalLight(0xfff6e5, 0.95)
  sun.position.set(-1.2, -1.5, 2.0).normalize()
  scene.add(ambient, sun)

  let rootGroup: THREE.Group | null = null
  let renderer: THREE.WebGLRenderer | null = null
  let anchorMerc = MercatorCoordinate.fromLngLat([-65.7, -33.3], 0)
  let meterScale = anchorMerc.meterInMercatorCoordinateUnits()

  const clearGroup = () => {
    if (!rootGroup) return
    rootGroup.traverse((obj) => {
      if (obj instanceof THREE.Mesh || obj instanceof THREE.Line) {
        obj.geometry?.dispose()
        if (Array.isArray(obj.material)) {
          obj.material.forEach((m) => m.dispose())
        } else {
          obj.material?.dispose()
        }
      }
    })
    scene.remove(rootGroup)
    rootGroup = null
  }

  const rebuild = (
    meshData: MeshOut | null,
    exaggeration: number,
    vis: LayerVisibility,
  ) => {
    clearGroup()
    if (!meshData || meshData.z_min === null || meshData.z_max === null) {
      getMap()?.triggerRepaint()
      return
    }

    const { rows, cols, lon, lat, z, in_field } = meshData
    if (rows < 2 || cols < 2) return

    const zBase = meshData.z_min
    const zSpan = Math.max(1e-3, meshData.z_max - meshData.z_min)

    // Anclar sistema local en el centro de la malla para mantener precisión Float32 en WebGL
    const midIdx = Math.floor((rows * cols) / 2)
    anchorMerc = MercatorCoordinate.fromLngLat(
      [lon[midIdx], lat[midIdx]],
      0,
    )
    meterScale = anchorMerc.meterInMercatorCoordinateUnits()

    rootGroup = new THREE.Group()

    if (vis.mesh3d) {
      const nVerts = rows * cols
      const positions = new Float32Array(nVerts * 3)
      const colors = new Float32Array(nVerts * 3)

      for (let i = 0; i < nVerts; i++) {
        const mc = MercatorCoordinate.fromLngLat([lon[i], lat[i]], 0)
        const zi = z[i]
        const dz = zi === null ? 0 : (zi - zBase) * exaggeration
        positions[3 * i] = (mc.x - anchorMerc.x) / meterScale
        positions[3 * i + 1] = (mc.y - anchorMerc.y) / meterScale
        positions[3 * i + 2] = dz

        const t = zi === null ? 0 : (zi - zBase) / zSpan
        const [r, g, b] = hypsometricColor(t, in_field[i])
        colors[3 * i] = r
        colors[3 * i + 1] = g
        colors[3 * i + 2] = b
      }

      const indices: number[] = []
      for (let r = 0; r < rows - 1; r++) {
        for (let c = 0; c < cols - 1; c++) {
          const i00 = r * cols + c
          const i01 = i00 + 1
          const i10 = (r + 1) * cols + c
          const i11 = i10 + 1
          if (
            z[i00] !== null &&
            z[i01] !== null &&
            z[i10] !== null &&
            z[i11] !== null
          ) {
            indices.push(i00, i10, i01, i01, i10, i11)
          }
        }
      }

      const geom = new THREE.BufferGeometry()
      geom.setAttribute('position', new THREE.BufferAttribute(positions, 3))
      geom.setAttribute('color', new THREE.BufferAttribute(colors, 3))
      geom.setIndex(indices)
      geom.computeVertexNormals()

      const mat = new THREE.MeshLambertMaterial({
        vertexColors: true,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.92,
        wireframe: vis.wireframe,
      })
      rootGroup.add(new THREE.Mesh(geom, mat))
    }

    if (vis.boundary && meshData.boundary.length > 0) {
      // Offset vertical anti-z-fighting (~1.5 % del desnivel o mínimo 1.5 m)
      const zOffset = Math.max(1.5, zSpan * 0.02 * exaggeration)
      for (const ring of meshData.boundary) {
        const pts: THREE.Vector3[] = []
        for (const v of ring) {
          const [lo, la, zv] = v
          if (lo === null || la === null) continue
          const mc = MercatorCoordinate.fromLngLat([lo, la], 0)
          const dz =
            (zv === null ? 0 : (zv - zBase) * exaggeration) + zOffset
          pts.push(
            new THREE.Vector3(
              (mc.x - anchorMerc.x) / meterScale,
              (mc.y - anchorMerc.y) / meterScale,
              dz,
            ),
          )
        }
        if (pts.length >= 2) {
          const lineGeom = new THREE.BufferGeometry().setFromPoints(pts)
          const lineMat = new THREE.LineBasicMaterial({
            color: 0x00ff88,
            linewidth: 2,
          })
          rootGroup.add(new THREE.Line(lineGeom, lineMat))
        }
      }
    }

    scene.add(rootGroup)
    getMap()?.triggerRepaint()
  }

  return {
    id: 'rotaterra-terrain-3d',
    type: 'custom',
    renderingMode: '3d',
    onAdd(map, gl) {
      renderer = new THREE.WebGLRenderer({
        canvas: map.getCanvas(),
        context: gl,
        antialias: true,
      })
      renderer.autoClear = false
    },
    render(_gl, options) {
      if (!renderer || !rootGroup) return
      const m = new THREE.Matrix4().fromArray(
        options.defaultProjectionData.mainMatrix as unknown as number[],
      )
      const l = new THREE.Matrix4()
        .makeTranslation(anchorMerc.x, anchorMerc.y, anchorMerc.z)
        .scale(new THREE.Vector3(meterScale, meterScale, meterScale))

      camera.projectionMatrix = m.multiply(l)
      renderer.resetState()
      renderer.render(scene, camera)
    },
    rebuild,
    disposeAll() {
      clearGroup()
      renderer?.dispose()
      renderer = null
    },
  }
}

export function TerrainScene3D({
  field,
  mesh,
  viewMode,
  exaggeration,
  layers,
  interactionMode,
  profileDraft,
  selectedPoint,
  onMapClick,
  onCursorMove,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const threeLayerRef = useRef<ThreeLayerController | null>(null)
  const clickHandlerRef = useRef(onMapClick)
  clickHandlerRef.current = onMapClick
  const moveHandlerRef = useRef(onCursorMove)
  moveHandlerRef.current = onCursorMove

  // Inicializar MapLibre + capa Three.js una sola vez
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      center: [-65.697, -33.3],
      zoom: 13,
      pitch: 55,
      bearing: -18,
      maxPitch: 78,
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
            attribution: '© OpenStreetMap contributors',
          },
          'field-2d': {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [] },
          },
          'profile-line': {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [] },
          },
          'selected-point': {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [] },
          },
        },
        layers: [
          {
            id: 'satellite-layer',
            type: 'raster',
            source: 'satellite',
            layout: { visibility: 'visible' },
          },
          {
            id: 'osm-layer',
            type: 'raster',
            source: 'osm',
            layout: { visibility: 'none' },
          },
          {
            id: 'field-2d-fill',
            type: 'fill',
            source: 'field-2d',
            paint: {
              'fill-color': '#10b981',
              'fill-opacity': 0.12,
            },
          },
          {
            id: 'field-2d-outline',
            type: 'line',
            source: 'field-2d',
            paint: {
              'line-color': '#34d399',
              'line-width': 2.5,
            },
          },
          {
            id: 'profile-line-layer',
            type: 'line',
            source: 'profile-line',
            paint: {
              'line-color': '#f59e0b',
              'line-width': 3,
              'line-dasharray': [2, 1],
            },
          },
          {
            id: 'selected-point-layer',
            type: 'circle',
            source: 'selected-point',
            paint: {
              'circle-radius': 6,
              'circle-color': '#38bdf8',
              'circle-stroke-width': 2,
              'circle-stroke-color': '#0f172a',
            },
          },
        ],
      },
    })

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left')

    const customLayer = createTerrainCustomLayer(() => mapRef.current)
    threeLayerRef.current = customLayer

    map.on('load', () => {
      map.addLayer(customLayer, 'profile-line-layer')
    })

    map.on('click', (e) => {
      clickHandlerRef.current(
        Number(e.lngLat.lng.toFixed(6)),
        Number(e.lngLat.lat.toFixed(6)),
      )
    })

    map.on('mousemove', (e) => {
      moveHandlerRef.current(
        Number(e.lngLat.lng.toFixed(6)),
        Number(e.lngLat.lat.toFixed(6)),
      )
    })

    mapRef.current = map
    return () => {
      customLayer.disposeAll()
      map.remove()
      mapRef.current = null
      threeLayerRef.current = null
    }
  }, [])

  // Centrar cámara y actualizar polígono 2D al cambiar de lote
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const updateSource = () => {
      const src = map.getSource('field-2d') as maplibregl.GeoJSONSource | undefined
      if (!src) return
      if (!field) {
        src.setData({ type: 'FeatureCollection', features: [] })
        return
      }
      src.setData({
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            properties: { name: field.name },
            geometry: field.geometry as GeoJSON.Geometry,
          },
        ],
      })
      const [w, s, e, n] = field.bbox
      map.fitBounds(
        [
          [w, s],
          [e, n],
        ],
        { padding: 70, duration: 750, pitch: viewMode === '3d' ? 55 : 0 },
      )
    }
    if (map.isStyleLoaded()) updateSource()
    else map.once('load', updateSource)
  }, [field?.id])

  // Alternar vista 2D cenital / perspectiva 3D
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (viewMode === '2d') {
      map.easeTo({ pitch: 0, bearing: 0, duration: 500 })
    } else {
      map.easeTo({ pitch: 55, bearing: -18, duration: 500 })
    }
  }, [viewMode])

  // Actualizar malla 3D, exageración y visibilidad de capas
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const apply = () => {
      map.setLayoutProperty(
        'satellite-layer',
        'visibility',
        layers.basemap === 'satellite' ? 'visible' : 'none',
      )
      map.setLayoutProperty(
        'osm-layer',
        'visibility',
        layers.basemap === 'osm' ? 'visible' : 'none',
      )
      map.setLayoutProperty(
        'field-2d-outline',
        'visibility',
        layers.boundary ? 'visible' : 'none',
      )
      threeLayerRef.current?.rebuild(mesh, exaggeration, layers)
    }
    if (map.isStyleLoaded()) apply()
    else map.once('load', apply)
  }, [mesh, exaggeration, layers])

  // Actualizar línea de perfil y punto inspeccionado
  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) return

    const profileSrc = map.getSource('profile-line') as
      | maplibregl.GeoJSONSource
      | undefined
    if (profileSrc) {
      profileSrc.setData({
        type: 'FeatureCollection',
        features:
          profileDraft.length >= 2
            ? [
                {
                  type: 'Feature',
                  properties: {},
                  geometry: {
                    type: 'LineString',
                    coordinates: profileDraft,
                  },
                },
              ]
            : [],
      })
    }

    const ptSrc = map.getSource('selected-point') as
      | maplibregl.GeoJSONSource
      | undefined
    if (ptSrc) {
      ptSrc.setData({
        type: 'FeatureCollection',
        features: selectedPoint
          ? [
              {
                type: 'Feature',
                properties: {},
                geometry: {
                  type: 'Point',
                  coordinates: [selectedPoint.lon, selectedPoint.lat],
                },
              },
            ]
          : [],
      })
    }
  }, [profileDraft, selectedPoint])

  return (
    <div className="map-stage">
      <div
        ref={containerRef}
        className={`map-canvas mode-${interactionMode}`}
      />
      {exaggeration !== 1 && (
        <div className="exaggeration-banner" role="status">
          Exageración vertical visual activa: <strong>{exaggeration}×</strong>{' '}
          (solo para visualización; las cotas, pendientes y perfiles se calculan
          siempre a escala real 1×).
        </div>
      )}
      {mesh && mesh.z_min !== null && mesh.z_max !== null && (
        <div className="hypsometric-legend">
          <span className="legend-title">Elevación DEM (m s.n.m.)</span>
          <div className="legend-gradient" />
          <div className="legend-labels">
            <span>{mesh.z_min.toFixed(1)} m</span>
            <span>
              {((mesh.z_min + mesh.z_max) / 2).toFixed(1)} m
            </span>
            <span>{mesh.z_max.toFixed(1)} m</span>
          </div>
        </div>
      )}
    </div>
  )
}
