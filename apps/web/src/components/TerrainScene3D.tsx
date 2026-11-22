import { useEffect, useRef } from 'react'
import * as maplibregl from 'maplibre-gl'
import {
  type CustomLayerInterface,
  MercatorCoordinate,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import * as THREE from 'three'
import type {
  FieldObservationOut,
  FieldOut,
  HydrologyOut,
  MeshOut,
  PointOut,
} from '../types/api'

export type InteractionMode = 'inspect' | 'profile' | 'observe'
export type BasemapMode = 'satellite' | 'osm'
export type SurfaceColorMode =
  | 'elevation'
  | 'hillshade'
  | 'slope'
  | 'mfd'
  | 'd8'
  | 'depressions'
  | 'subbasins'
  | 'runoff'
  | 'twi'
  | 'spi'
  | 'water_depth'
  | 'velocity'
  | 'agronomic_zones'
  | 'erosion'
  | 'ndvi'

export interface LayerVisibility {
  basemap: BasemapMode
  surfaceColor: SurfaceColorMode
  mesh3d: boolean
  wireframe: boolean
  boundary: boolean
  contours: boolean
  drainageNetwork: boolean
  depressionsAndOutlets: boolean
}

interface Props {
  field: FieldOut | null
  mesh: MeshOut | null
  hydrology: HydrologyOut | null
  observations: FieldObservationOut[]
  particlePaths: number[][][]
  showParticles: boolean
  transitFraction: number
  viewMode: '2d' | '3d'
  exaggeration: number
  layers: LayerVisibility
  interactionMode: InteractionMode
  profileDraft: [number, number][]
  selectedPoint: PointOut | null
  onMapClick: (lon: number, lat: number) => void
  onCursorMove: (lon: number, lat: number) => void
}

function attenuateOutside(
  r: number,
  g: number,
  b: number,
  inField: boolean,
): [number, number, number] {
  if (inField) return [r, g, b]
  const gray = 0.3 * r + 0.59 * g + 0.11 * b
  return [
    0.55 * r + 0.45 * gray,
    0.55 * g + 0.45 * gray,
    0.55 * b + 0.45 * gray,
  ]
}

/** Gradiente hipsométrico (verde bajo -> ocre medio -> marrón/crema alto). */
function hypsometricColor(t: number, inField: boolean): [number, number, number] {
  const u = Math.min(1, Math.max(0, t))
  let r: number
  let g: number
  let b: number
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
  return attenuateOutside(r, g, b, inField)
}

/** Gradiente de pendiente (%): verde suave -> amarillo -> naranja -> rojo. */
function slopeColor(slopePct: number | null, inField: boolean): [number, number, number] {
  const s = slopePct ?? 0
  const u = Math.min(1, Math.max(0, s / 8.0))
  let r: number
  let g: number
  let b: number
  if (u < 0.5) {
    const k = u / 0.5
    r = 0.16 + 0.78 * k
    g = 0.65 + 0.15 * k
    b = 0.32 - 0.20 * k
  } else {
    const k = (u - 0.5) / 0.5
    r = 0.94
    g = 0.80 - 0.62 * k
    b = 0.12
  }
  return attenuateOutside(r, g, b, inField)
}

/** Gradiente logarítmico de acumulación de flujo (ha): gris pizarra -> celeste -> cian -> azul intenso. */
function flowAccumColor(
  areaHa: number | null,
  maxHa: number,
  inField: boolean,
): [number, number, number] {
  const a = Math.max(0, areaHa ?? 0)
  const denom = Math.log10(1 + Math.max(0.5, maxHa) * 20)
  const u = Math.min(1, Math.max(0, Math.log10(1 + a * 20) / denom))
  const r = 0.20 * (1 - u) + 0.05 * u
  const g = 0.27 * (1 - u) + 0.78 * u
  const b = 0.34 * (1 - u) + 0.98 * u
  return attenuateOutside(r, g, b, inField)
}

/** Color de profundidad de depresión (m): terreno neutro -> magenta/violeta en bajos. */
function depressionColor(
  sinkDepthM: number | null,
  hsVal: number | null,
  inField: boolean,
): [number, number, number] {
  const d = sinkDepthM ?? 0
  const base = 0.28 + 0.45 * (hsVal ?? 0.65)
  if (d <= 0.05) {
    return attenuateOutside(base * 0.85, base * 0.95, base * 0.85, inField)
  }
  const u = Math.min(1, d / 1.0)
  const r = 0.55 + 0.40 * u
  const g = 0.22 * (1 - u)
  const b = 0.75 + 0.22 * u
  return attenuateOutside(r, g, b, inField)
}

const SUBBASIN_PALETTE: [number, number, number][] = [
  [0.22, 0.74, 0.97],
  [0.20, 0.83, 0.60],
  [0.98, 0.75, 0.14],
  [0.96, 0.45, 0.71],
  [0.65, 0.55, 0.98],
  [0.98, 0.57, 0.24],
  [0.38, 0.65, 0.98],
  [0.52, 0.80, 0.09],
]

function subbasinColor(
  basinId: number | null | undefined,
  hsVal: number | null,
  inField: boolean,
): [number, number, number] {
  const shade = 0.55 + 0.45 * (hsVal ?? 0.7)
  if (!basinId || basinId <= 0) {
    return attenuateOutside(0.32 * shade, 0.36 * shade, 0.42 * shade, inField)
  }
  const [r, g, b] = SUBBASIN_PALETTE[(basinId - 1) % SUBBASIN_PALETTE.length]
  return attenuateOutside(r * shade, g * shade, b * shade, inField)
}

/** Gradiente de carga de escorrentía estimada (mm equiv., escala log): ámbar suave -> turquesa -> azul cobalto. */
function runoffLoadColor(
  loadMm: number | null,
  maxLoadMm: number,
  inField: boolean,
): [number, number, number] {
  const v = Math.max(0, loadMm ?? 0)
  if (v <= 0.05) {
    return attenuateOutside(0.28, 0.32, 0.36, inField)
  }
  const denom = Math.log10(1 + Math.max(10, maxLoadMm))
  const u = Math.min(1, Math.max(0, Math.log10(1 + v) / denom))
  let r: number
  let g: number
  let b: number
  if (u < 0.5) {
    const k = u / 0.5
    r = 0.92 - 0.72 * k
    g = 0.78 + 0.08 * k
    b = 0.32 + 0.56 * k
  } else {
    const k = (u - 0.5) / 0.5
    r = 0.20 - 0.14 * k
    g = 0.86 - 0.38 * k
    b = 0.88 + 0.10 * k
  }
  return attenuateOutside(r, g, b, inField)
}

/** Color TWI (humedad topográfica): ocre seco -> verde -> azul húmedo. */
function twiColor(
  twiVal: number | null,
  inField: boolean,
): [number, number, number] {
  const v = twiVal ?? 5.0
  const u = Math.min(1, Math.max(0, (v - 4.0) / 8.0))
  const r = 0.78 * (1 - u) + 0.08 * u
  const g = 0.65 * (1 - u) + 0.58 * u
  const b = 0.25 * (1 - u) + 0.96 * u
  return attenuateOutside(r, g, b, inField)
}

/** Color SPI (potencia erosiva): gris verdoso -> amarillo -> rojo intenso. */
function spiColor(
  spiVal: number | null,
  maxSpi: number,
  inField: boolean,
): [number, number, number] {
  const v = Math.max(0, spiVal ?? 0)
  const denom = Math.log10(1 + Math.max(2, maxSpi) * 10)
  const u = Math.min(1, Math.max(0, Math.log10(1 + v * 10) / denom))
  const r = 0.25 + 0.73 * u
  const g = 0.60 * (1 - u * 0.75)
  const b = 0.25 * (1 - u)
  return attenuateOutside(r, g, b, inField)
}

/** Color de lámina de agua 2D simulada (water_depth_m, Fase 4). */
function waterDepth2DColor(
  depthM: number | null,
  hsVal: number | null,
  inField: boolean,
): [number, number, number] {
  const d = depthM ?? 0
  const base = 0.30 + 0.45 * (hsVal ?? 0.65)
  if (d < 0.01) {
    return attenuateOutside(base * 0.9, base * 0.95, base * 0.85, inField)
  }
  const u = Math.min(1, d / 0.35)
  const r = 0.18 * (1 - u) + 0.03 * u
  const g = 0.78 * (1 - u) + 0.38 * u
  const b = 0.95
  return attenuateOutside(r, g, b, inField)
}

/** Color de ambientes hidro-agronómicos RotaTerra (Fase 5: 1=Loma, 2=Media loma, 3=Vía conc., 4=Bajo). */
function agronomicZoneColor(
  zoneId: number | null | undefined,
  hsVal: number | null,
  inField: boolean,
): [number, number, number] {
  const shade = 0.62 + 0.38 * (hsVal ?? 0.7)
  let rgb: [number, number, number] = [0.45, 0.50, 0.55]
  if (zoneId === 1) rgb = [0.88, 0.74, 0.32] // Loma bien drenada (dorado)
  else if (zoneId === 2) rgb = [0.22, 0.76, 0.44] // Media loma (verde)
  else if (zoneId === 3) rgb = [0.96, 0.48, 0.16] // Vía escurrimiento (naranja erosivo)
  else if (zoneId === 4) rgb = [0.20, 0.52, 0.96] // Bajo anegable (azul)
  return attenuateOutside(rgb[0] * shade, rgb[1] * shade, rgb[2] * shade, inField)
}

/** Color de NDVI (vigor vegetativo): marrón suelo desnudo -> amarillo -> verde intenso. */
function ndviColor(
  ndviVal: number | null,
  inField: boolean,
): [number, number, number] {
  const v = ndviVal ?? 0.35
  const u = Math.min(1, Math.max(0, (v - 0.15) / 0.65))
  let r: number
  let g: number
  let b: number
  if (u < 0.45) {
    const k = u / 0.45
    r = 0.78 + 0.14 * k
    g = 0.32 + 0.48 * k
    b = 0.16
  } else {
    const k = (u - 0.45) / 0.55
    r = 0.92 - 0.80 * k
    g = 0.80 - 0.12 * k
    b = 0.16 + 0.10 * k
  }
  return attenuateOutside(r, g, b, inField)
}

interface ThreeLayerController extends CustomLayerInterface {
  rebuild: (
    meshData: MeshOut | null,
    exaggeration: number,
    vis: LayerVisibility,
    particlePaths: number[][][],
    showParticles: boolean,
    transitFraction: number,
  ) => void
  disposeAll: () => void
}

function createTerrainCustomLayer(
  getMap: () => maplibregl.Map | null,
): ThreeLayerController {
  const camera = new THREE.Camera()
  const scene = new THREE.Scene()

  const ambient = new THREE.AmbientLight(0xffffff, 0.78)
  const sun = new THREE.DirectionalLight(0xfff6e5, 0.92)
  sun.position.set(-1.2, -1.5, 2.0).normalize()
  scene.add(ambient, sun)

  let rootGroup: THREE.Group | null = null
  let particlesPoints: THREE.Points | null = null
  let localPaths: THREE.Vector3[][] = []
  let activeFraction = 1.0
  let animFrameId: number | null = null
  let renderer: THREE.WebGLRenderer | null = null
  let anchorMerc = MercatorCoordinate.fromLngLat([-65.7, -33.3], 0)
  let meterScale = anchorMerc.meterInMercatorCoordinateUnits()

  const stopAnim = () => {
    if (animFrameId !== null) {
      window.cancelAnimationFrame(animFrameId)
      animFrameId = null
    }
  }

  const clearGroup = () => {
    stopAnim()
    particlesPoints = null
    localPaths = []
    if (!rootGroup) return
    rootGroup.traverse((obj) => {
      if (
        obj instanceof THREE.Mesh ||
        obj instanceof THREE.Line ||
        obj instanceof THREE.Points
      ) {
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
    particlePaths: number[][][],
    showParticles: boolean,
    transitFraction: number,
  ) => {
    clearGroup()
    activeFraction = Math.max(0.05, Math.min(1.0, transitFraction))
    if (!meshData || meshData.z_min === null || meshData.z_max === null) {
      getMap()?.triggerRepaint()
      return
    }

    const { rows, cols, lon, lat, z, in_field } = meshData
    if (rows < 2 || cols < 2) return

    const zBase = meshData.z_min
    const zSpan = Math.max(1e-3, meshData.z_max - meshData.z_min)

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

      const mfdArr = meshData.mfd_area_ha
      const d8Arr = meshData.d8_area_ha
      const sinkArr = meshData.sink_depth_m
      const basArr = meshData.subbasin_id
      const runoffArr = meshData.runoff_load_mm
      const twiArr = meshData.twi
      const spiArr = meshData.spi
      const wdArr = meshData.water_depth_m
      const velArr = meshData.velocity_m_s
      const zoneArr = meshData.agronomic_zone_id
      const lossArr = meshData.soil_loss_t_ha
      const ndviArr = meshData.ndvi
      const slopeArr = meshData.slope_pct
      const hsArr = meshData.hillshade

      let maxMfd = 1.0
      if (mfdArr) {
        for (const v of mfdArr) if (v !== null && v > maxMfd) maxMfd = v
      }
      let maxD8 = 1.0
      if (d8Arr) {
        for (const v of d8Arr) if (v !== null && v > maxD8) maxD8 = v
      }
      let maxRunoff = 20.0
      if (runoffArr) {
        for (const v of runoffArr) if (v !== null && v > maxRunoff) maxRunoff = v
      }
      let maxSpi = 2.0
      if (spiArr) {
        for (const v of spiArr) if (v !== null && v > maxSpi) maxSpi = v
      }

      for (let i = 0; i < nVerts; i++) {
        const mc = MercatorCoordinate.fromLngLat([lon[i], lat[i]], 0)
        const zi = z[i]
        const dz = zi === null ? 0 : (zi - zBase) * exaggeration
        positions[3 * i] = (mc.x - anchorMerc.x) / meterScale
        positions[3 * i + 1] = (mc.y - anchorMerc.y) / meterScale
        positions[3 * i + 2] = dz

        const inside = in_field[i]
        let rgb: [number, number, number]
        switch (vis.surfaceColor) {
          case 'hillshade': {
            const h = hsArr?.[i] ?? 0.65
            rgb = attenuateOutside(h, h, h, inside)
            break
          }
          case 'slope':
            rgb = slopeColor(slopeArr?.[i] ?? null, inside)
            break
          case 'mfd':
            rgb = flowAccumColor(mfdArr?.[i] ?? null, maxMfd, inside)
            break
          case 'd8':
            rgb = flowAccumColor(d8Arr?.[i] ?? null, maxD8, inside)
            break
          case 'depressions':
            rgb = depressionColor(
              sinkArr?.[i] ?? null,
              hsArr?.[i] ?? null,
              inside,
            )
            break
          case 'subbasins':
            rgb = subbasinColor(
              basArr?.[i] ?? null,
              hsArr?.[i] ?? null,
              inside,
            )
            break
          case 'runoff':
            rgb = runoffLoadColor(
              runoffArr?.[i] !== null && runoffArr?.[i] !== undefined
                ? (runoffArr[i] as number) * activeFraction
                : null,
              maxRunoff,
              inside,
            )
            break
          case 'twi':
            rgb = twiColor(twiArr?.[i] ?? null, inside)
            break
          case 'spi':
            rgb = spiColor(spiArr?.[i] ?? null, maxSpi, inside)
            break
          case 'water_depth':
            rgb = waterDepth2DColor(
              wdArr?.[i] !== null && wdArr?.[i] !== undefined
                ? (wdArr[i] as number) * activeFraction
                : null,
              hsArr?.[i] ?? null,
              inside,
            )
            break
          case 'velocity':
            rgb = slopeColor(
              velArr?.[i] !== null && velArr?.[i] !== undefined
                ? (velArr[i] as number) * 10.0 * activeFraction
                : null,
              inside,
            )
            break
          case 'agronomic_zones':
            rgb = agronomicZoneColor(
              zoneArr?.[i] ?? null,
              hsArr?.[i] ?? null,
              inside,
            )
            break
          case 'erosion':
            rgb = slopeColor(
              lossArr?.[i] !== null && lossArr?.[i] !== undefined
                ? (lossArr[i] as number) * 2.5
                : null,
              inside,
            )
            break
          case 'ndvi':
            rgb = ndviColor(ndviArr?.[i] ?? null, inside)
            break
          case 'elevation':
          default: {
            const t = zi === null ? 0 : (zi - zBase) / zSpan
            rgb = hypsometricColor(t, inside)
            break
          }
        }
        colors[3 * i] = rgb[0]
        colors[3 * i + 1] = rgb[1]
        colors[3 * i + 2] = rgb[2]
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
        opacity: 0.93,
        wireframe: vis.wireframe,
      })
      rootGroup.add(new THREE.Mesh(geom, mat))
    }

    if (vis.boundary && meshData.boundary.length > 0) {
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

    // Construir partículas 3D vinculadas a las rutas de flujo calculadas (Fase 3, SDD §4.5 y §7.3)
    if (showParticles && particlePaths.length > 0) {
      const zOffsetPart = Math.max(2.2, zSpan * 0.03 * exaggeration)
      localPaths = particlePaths
        .map((path) =>
          path.map(([lo, la, zv]) => {
            const mc = MercatorCoordinate.fromLngLat([lo, la], 0)
            const dz = ((zv - zBase) * exaggeration) + zOffsetPart
            return new THREE.Vector3(
              (mc.x - anchorMerc.x) / meterScale,
              (mc.y - anchorMerc.y) / meterScale,
              dz,
            )
          }),
        )
        .filter((p) => p.length >= 2)

      const particlesPerPath = 4
      const activePathsCount = Math.max(
        1,
        Math.round(localPaths.length * activeFraction),
      )
      const totalParticles = activePathsCount * particlesPerPath
      const partPositions = new Float32Array(totalParticles * 3)
      const partGeom = new THREE.BufferGeometry()
      partGeom.setAttribute(
        'position',
        new THREE.BufferAttribute(partPositions, 3),
      )
      const partMat = new THREE.PointsMaterial({
        color: 0x38bdf8,
        size: 5.5,
        sizeAttenuation: false,
      })
      particlesPoints = new THREE.Points(partGeom, partMat)
      rootGroup.add(particlesPoints)

      const stepParticles = (nowMs: number) => {
        if (!particlesPoints || localPaths.length === 0) return
        const posAttr = particlesPoints.geometry.getAttribute(
          'position',
        ) as THREE.BufferAttribute
        const arr = posAttr.array as Float32Array
        const cycleSpeed = 0.00025 * (0.45 + 0.85 * activeFraction)
        let idx = 0
        for (let pIdx = 0; pIdx < activePathsCount; pIdx++) {
          const path = localPaths[pIdx]
          const segs = path.length - 1
          for (let k = 0; k < particlesPerPath; k++) {
            const phase =
              (nowMs * cycleSpeed + k / particlesPerPath + pIdx * 0.13) % 1.0
            const fIdx = phase * segs
            const s0 = Math.min(segs - 1, Math.floor(fIdx))
            const frac = fIdx - s0
            const v0 = path[s0]
            const v1 = path[s0 + 1]
            arr[3 * idx] = v0.x + (v1.x - v0.x) * frac
            arr[3 * idx + 1] = v0.y + (v1.y - v0.y) * frac
            arr[3 * idx + 2] = v0.z + (v1.z - v0.z) * frac
            idx++
          }
        }
        posAttr.needsUpdate = true
        getMap()?.triggerRepaint()
        animFrameId = window.requestAnimationFrame(stepParticles)
      }
      animFrameId = window.requestAnimationFrame(stepParticles)
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
  hydrology,
  observations,
  particlePaths,
  showParticles,
  transitFraction,
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
          contours: {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [] },
          },
          'drainage-network': {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [] },
          },
          'hydro-points': {
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
          'field-observations': {
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
              'fill-opacity': 0.1,
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
            id: 'contours-layer',
            type: 'line',
            source: 'contours',
            paint: {
              'line-color': '#fde68a',
              'line-width': 1.2,
              'line-opacity': 0.75,
            },
          },
          {
            id: 'drainage-network-layer',
            type: 'line',
            source: 'drainage-network',
            paint: {
              'line-color': '#38bdf8',
              'line-width': 2.8,
              'line-opacity': 0.95,
            },
          },
          {
            id: 'hydro-points-layer',
            type: 'circle',
            source: 'hydro-points',
            paint: {
              'circle-radius': 6,
              'circle-color': [
                'match',
                ['get', 'kind'],
                'depression',
                '#d946ef',
                '#22d3ee',
              ],
              'circle-stroke-width': 2,
              'circle-stroke-color': '#0f172a',
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
          {
            id: 'field-observations-layer',
            type: 'circle',
            source: 'field-observations',
            paint: {
              'circle-radius': 7,
              'circle-color': '#f97316',
              'circle-stroke-width': 2,
              'circle-stroke-color': '#ffffff',
            },
          },
        ],
      },
    })

    map.addControl(
      new maplibregl.NavigationControl({ visualizePitch: true }),
      'top-right',
    )
    map.addControl(
      new maplibregl.ScaleControl({ unit: 'metric' }),
      'bottom-left',
    )

    const customLayer = createTerrainCustomLayer(() => mapRef.current)
    threeLayerRef.current = customLayer

    map.on('load', () => {
      map.addLayer(customLayer, 'contours-layer')
    })

    map.on('click', (e: maplibregl.MapMouseEvent) => {
      clickHandlerRef.current(
        Number(e.lngLat.lng.toFixed(6)),
        Number(e.lngLat.lat.toFixed(6)),
      )
    })

    map.on('mousemove', (e: maplibregl.MapMouseEvent) => {
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

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const updateSource = () => {
      const src = map.getSource('field-2d') as
        | maplibregl.GeoJSONSource
        | undefined
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

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (viewMode === '2d') {
      map.easeTo({ pitch: 0, bearing: 0, duration: 500 })
    } else {
      map.easeTo({ pitch: 55, bearing: -18, duration: 500 })
    }
  }, [viewMode])

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
      map.setLayoutProperty(
        'contours-layer',
        'visibility',
        layers.contours ? 'visible' : 'none',
      )
      map.setLayoutProperty(
        'drainage-network-layer',
        'visibility',
        layers.drainageNetwork ? 'visible' : 'none',
      )
      map.setLayoutProperty(
        'hydro-points-layer',
        'visibility',
        layers.depressionsAndOutlets ? 'visible' : 'none',
      )
      threeLayerRef.current?.rebuild(
        mesh,
        exaggeration,
        layers,
        particlePaths,
        showParticles,
        transitFraction,
      )
    }
    if (map.isStyleLoaded()) apply()
    else map.once('load', apply)
  }, [
    mesh,
    exaggeration,
    layers,
    particlePaths,
    showParticles,
    transitFraction,
  ])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const updateObs = () => {
      const obsSrc = map.getSource('field-observations') as
        | maplibregl.GeoJSONSource
        | undefined
      if (!obsSrc) return
      obsSrc.setData({
        type: 'FeatureCollection',
        features: observations.map((o) => ({
          type: 'Feature',
          properties: { id: o.id, label: o.label, notes: o.notes },
          geometry: { type: 'Point', coordinates: [o.lon, o.lat] },
        })),
      })
    }
    if (map.isStyleLoaded()) updateObs()
    else map.once('load', updateObs)
  }, [observations])

  // Poblar fuentes GeoJSON de hidrología estática (curvas de nivel, red de drenaje, depresiones y salidas)
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const updateHydro = () => {
      const contoursSrc = map.getSource('contours') as
        | maplibregl.GeoJSONSource
        | undefined
      const netSrc = map.getSource('drainage-network') as
        | maplibregl.GeoJSONSource
        | undefined
      const ptsSrc = map.getSource('hydro-points') as
        | maplibregl.GeoJSONSource
        | undefined

      if (!hydrology) {
        contoursSrc?.setData({ type: 'FeatureCollection', features: [] })
        netSrc?.setData({ type: 'FeatureCollection', features: [] })
        ptsSrc?.setData({ type: 'FeatureCollection', features: [] })
        return
      }

      contoursSrc?.setData(hydrology.contours as GeoJSON.FeatureCollection)
      netSrc?.setData(hydrology.drainage_network)

      const ptFeatures: GeoJSON.Feature[] = [
        ...hydrology.depressions
          .filter((d) => d.in_field)
          .map((d) => ({
            type: 'Feature' as const,
            properties: {
              kind: 'depression',
              id: d.id,
              depth_m: d.max_depth_m,
            },
            geometry: {
              type: 'Point' as const,
              coordinates: [d.centroid_lon, d.centroid_lat],
            },
          })),
        ...hydrology.outlets.map((o) => ({
          type: 'Feature' as const,
          properties: {
            kind: 'outlet',
            id: o.id,
            area_ha: o.contributing_area_mfd_ha,
          },
          geometry: {
            type: 'Point' as const,
            coordinates: [o.lon, o.lat],
          },
        })),
      ]
      ptsSrc?.setData({
        type: 'FeatureCollection',
        features: ptFeatures,
      })
    }
    if (map.isStyleLoaded()) updateHydro()
    else map.once('load', updateHydro)
  }, [hydrology])

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
          (solo para visualización; las cotas, pendientes, acumulaciones y
          perfiles se calculan siempre a escala real 1×).
        </div>
      )}
      {mesh && mesh.z_min !== null && mesh.z_max !== null && (
        <div className="hypsometric-legend">
          {layers.surfaceColor === 'elevation' && (
            <>
              <span className="legend-title">Elevación DEM (m s.n.m.)</span>
              <div className="legend-gradient" />
              <div className="legend-labels">
                <span>{mesh.z_min.toFixed(1)} m</span>
                <span>{((mesh.z_min + mesh.z_max) / 2).toFixed(1)} m</span>
                <span>{mesh.z_max.toFixed(1)} m</span>
              </div>
            </>
          )}
          {layers.surfaceColor === 'slope' && (
            <>
              <span className="legend-title">Pendiente local (%)</span>
              <div className="legend-gradient legend-slope" />
              <div className="legend-labels">
                <span>0 %</span>
                <span>4 %</span>
                <span>≥ 8 %</span>
              </div>
            </>
          )}
          {layers.surfaceColor === 'hillshade' && (
            <>
              <span className="legend-title">
                Sombreado relieve (NW 315° / 45°)
              </span>
              <div className="legend-gradient legend-hillshade" />
              <div className="legend-labels">
                <span>Sombra</span>
                <span>Iluminado</span>
              </div>
            </>
          )}
          {(layers.surfaceColor === 'mfd' || layers.surfaceColor === 'd8') && (
            <>
              <span className="legend-title">
                Área contribuyente {layers.surfaceColor.toUpperCase()} (ha,
                log)
              </span>
              <div className="legend-gradient legend-flow" />
              <div className="legend-labels">
                <span>Cabecera</span>
                <span>Concentración</span>
              </div>
            </>
          )}
          {layers.surfaceColor === 'depressions' && (
            <>
              <span className="legend-title">
                Profundidad de depresiones (m)
              </span>
              <div className="legend-gradient legend-depressions" />
              <div className="legend-labels">
                <span>0 m</span>
                <span>0,5 m</span>
                <span>≥ 1,0 m</span>
              </div>
            </>
          )}
          {layers.surfaceColor === 'subbasins' && (
            <>
              <span className="legend-title">
                Subcuencas por punto de salida
              </span>
              <div className="legend-labels">
                <span>Colores discretos por salida principal del lote</span>
              </div>
            </>
          )}
          {layers.surfaceColor === 'runoff' && (
            <>
              <span className="legend-title">
                Carga escorrentía NRCS-CN + MFD (mm equiv., no inundación)
              </span>
              <div className="legend-gradient legend-runoff" />
              <div className="legend-labels">
                <span>Ladera (Q)</span>
                <span>Vías de concentración</span>
              </div>
            </>
          )}
          {layers.surfaceColor === 'twi' && (
            <>
              <span className="legend-title">
                Índice de Humedad Topográfica (TWI = ln(a/tan β))
              </span>
              <div className="legend-gradient legend-runoff" />
              <div className="legend-labels">
                <span>Loma seca</span>
                <span>Propensión a humedad</span>
              </div>
            </>
          )}
          {layers.surfaceColor === 'spi' && (
            <>
              <span className="legend-title">
                Índice de Potencia Erosiva (SPI = a · tan β)
              </span>
              <div className="legend-gradient legend-slope" />
              <div className="legend-labels">
                <span>Baja energía</span>
                <span>Riesgo erosión concentrada</span>
              </div>
            </>
          )}
          {layers.surfaceColor === 'water_depth' && (
            <>
              <span className="legend-title">
                Profundidad de agua simulada 2D Manning (water_depth_m)
              </span>
              <div className="legend-gradient legend-flow" />
              <div className="legend-labels">
                <span>0,00 m</span>
                <span>0,15 m</span>
                <span>≥ 0,35 m</span>
              </div>
            </>
          )}
          {layers.surfaceColor === 'velocity' && (
            <>
              <span className="legend-title">
                Velocidad superficial 2D Manning (velocity_m_s)
              </span>
              <div className="legend-gradient legend-slope" />
              <div className="legend-labels">
                <span>0,0 m/s</span>
                <span>0,4 m/s</span>
                <span>≥ 0,8 m/s</span>
              </div>
            </>
          )}
          {layers.surfaceColor === 'agronomic_zones' && (
            <>
              <span className="legend-title">
                Ambientes Hidro-Agronómicos RotaTerra (Fase 5)
              </span>
              <div className="legend-labels">
                <span>1: Loma (dorado) · 2: Media (verde)</span>
              </div>
              <div className="legend-labels">
                <span>3: Vía conc. (naranja) · 4: Bajo (azul)</span>
              </div>
            </>
          )}
          {layers.surfaceColor === 'erosion' && (
            <>
              <span className="legend-title">
                Pérdida de suelo por tormenta USLE (t/ha)
              </span>
              <div className="legend-gradient legend-slope" />
              <div className="legend-labels">
                <span>0 t/ha</span>
                <span>1,5 t/ha</span>
                <span>≥ 3,5 t/ha</span>
              </div>
            </>
          )}
          {layers.surfaceColor === 'ndvi' && (
            <>
              <span className="legend-title">
                Monitor de Vigor Vegetativo (NDVI)
              </span>
              <div className="legend-gradient" />
              <div className="legend-labels">
                <span>&lt; 0,30 (Débil)</span>
                <span>0,50</span>
                <span>&gt; 0,75 (Alto)</span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
