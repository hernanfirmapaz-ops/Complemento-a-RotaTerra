import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { FieldOut, MeshOut } from '../types/api'

export type AgronomistOverlayMode =
  | 'satellite_water'
  | 'waterlogging'
  | 'erosion'
  | 'environments'
  | 'ndvi'

interface Props {
  field: FieldOut | null
  mesh: MeshOut | null
  overlayMode: AgronomistOverlayMode
  exaggeration: number
  rainIntensityFactor: number // 0..2 (0 = sin lluvia, 1 = tormenta 80 mm, 1.6 = temporal 120 mm)
  showBoundary: boolean
  showContours: boolean
  isPlayingRain: boolean
  onPointInspect?: (lon: number, lat: number) => void
}

/** Convierte lon/lat a coordenadas de tile XYZ Web Mercator fraccionarias. */
function lonLatToTileXY(lon: number, lat: number, zoom: number): [number, number] {
  const n = Math.pow(2, zoom)
  const x = ((lon + 180) / 360) * n
  const latRad = (lat * Math.PI) / 180
  const y =
    ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n
  return [x, y]
}

/** Sintetiza una textura satelital fotorrealista de alta resolución (1024x1024) a partir del relieve real, pendiente, orientación y NDVI, y superpone tiles Esri World Imagery si hay conexión externa. */
async function buildSatelliteCanvasTexture(
  mesh: MeshOut,
  west: number,
  south: number,
  east: number,
  north: number,
): Promise<HTMLCanvasElement> {
  const outCanvas = document.createElement('canvas')
  outCanvas.width = 1024
  outCanvas.height = 1024
  const oCtx = outCanvas.getContext('2d')!

  // 1. Pintar base satelital fotorrealista de alta definición a partir de elevación, pendiente, aspecto y NDVI del lote
  const { rows, cols, z, slope_pct, ndvi, mfd_area_ha } = mesh
  const zMin = mesh.z_min ?? 0
  const zMax = mesh.z_max ?? zMin + 1
  const zSpan = Math.max(1, zMax - zMin)

  const imgData = oCtx.createImageData(1024, 1024)
  const data = imgData.data

  for (let py = 0; py < 1024; py++) {
    const v = py / 1023
    const rf = v * (rows - 1)
    const r0 = Math.min(rows - 2, Math.max(0, Math.floor(rf)))
    const fr = rf - r0

    for (let px = 0; px < 1024; px++) {
      const u = px / 1023
      const cf = u * (cols - 1)
      const c0 = Math.min(cols - 2, Math.max(0, Math.floor(cf)))
      const fc = cf - c0

      const i00 = r0 * cols + c0
      const i10 = i00 + 1
      const i01 = i00 + cols
      const i11 = i01 + 1

      const z00 = z[i00] ?? zMin
      const z10 = z[i10] ?? zMin
      const z01 = z[i01] ?? zMin
      const z11 = z[i11] ?? zMin
      const zVal =
        z00 * (1 - fc) * (1 - fr) +
        z10 * fc * (1 - fr) +
        z01 * (1 - fc) * fr +
        z11 * fc * fr
      const elevNorm = Math.min(1, Math.max(0, (zVal - zMin) / zSpan))

      const s00 = slope_pct[i00] ?? 3
      const s10 = slope_pct[i10] ?? 3
      const s01 = slope_pct[i01] ?? 3
      const s11 = slope_pct[i11] ?? 3
      const slopeVal =
        s00 * (1 - fc) * (1 - fr) +
        s10 * fc * (1 - fr) +
        s01 * (1 - fc) * fr +
        s11 * fc * fr

      const nv = ndvi ? (ndvi[i00] ?? 0.45) : 0.45
      const acc = mfd_area_ha ? (mfd_area_ha[i00] ?? 0) : 0

      // Sombreado analítico (hillshade) desde el noroeste para dar volumen fotográfico
      const dzdx = z10 - z00
      const dzdy = z01 - z00
      const shade = Math.min(
        1.28,
        Math.max(0.58, 0.94 + (-dzdx * 0.65 - dzdy * 0.55) / Math.max(1.5, zSpan * 0.045)),
      )

      // Micro-textura orgánica suave (sin bloques) para simular cobertura vegetal y suelo
      const noise =
        Math.sin(px * 0.17 + py * 0.11) * Math.cos(px * 0.09 - py * 0.19) * 8 +
        Math.sin(px * 0.43 + py * 0.37) * 4

      // Paleta satelital natural tipo piedemonte/agrícola (como Caso #1327: monte verde oliva oscuro en altura y quebradas,
      // suelo ocre/tostado en faldeos y parcelas agrícolas)
      const vegWeight = Math.min(
        1,
        Math.max(0, elevNorm * 0.55 + (nv - 0.3) * 0.8 + (acc > 0.35 ? 0.3 : 0) + (slopeVal > 5 ? 0.25 : 0)),
      )

      // Color suelo agrícola / rastrojo ocre tostado (RGB ~ 168, 144, 108)
      const soilR = 166 - slopeVal * 1.4
      const soilG = 142 - slopeVal * 1.2
      const soilB = 104 - slopeVal * 1.0

      // Color monte / vegetación verde oliva oscuro (RGB ~ 66, 86, 56)
      const vegR = 62 + elevNorm * 18
      const vegG = 84 + elevNorm * 22
      const vegB = 52 + elevNorm * 14

      let rCol = (soilR * (1 - vegWeight) + vegR * vegWeight) * shade + noise
      let gCol = (soilG * (1 - vegWeight) + vegG * vegWeight) * shade + noise
      let bCol = (soilB * (1 - vegWeight) + vegB * vegWeight) * shade + noise * 0.8

      const pIdx = (py * 1024 + px) * 4
      data[pIdx] = Math.min(255, Math.max(20, Math.round(rCol)))
      data[pIdx + 1] = Math.min(255, Math.max(22, Math.round(gCol)))
      data[pIdx + 2] = Math.min(255, Math.max(18, Math.round(bCol)))
      data[pIdx + 3] = 255
    }
  }
  oCtx.putImageData(imgData, 0, 0)

  // 2. Intentar superponer tiles satelitales Esri World Imagery reales si la red los permite
  let zoom = 16
  let [xMinF, yMinF] = lonLatToTileXY(west, north, zoom)
  let [xMaxF, yMaxF] = lonLatToTileXY(east, south, zoom)
  if (Math.ceil(xMaxF) - Math.floor(xMinF) > 6 || Math.ceil(yMaxF) - Math.floor(yMinF) > 6) {
    zoom = 15
    ;[xMinF, yMinF] = lonLatToTileXY(west, north, zoom)
    ;[xMaxF, yMaxF] = lonLatToTileXY(east, south, zoom)
  }

  const tx0 = Math.floor(xMinF)
  const ty0 = Math.floor(yMinF)
  const tx1 = Math.floor(xMaxF)
  const ty1 = Math.floor(yMaxF)
  const tCols = tx1 - tx0 + 1
  const tRows = ty1 - ty0 + 1

  const stitchCanvas = document.createElement('canvas')
  stitchCanvas.width = tCols * 256
  stitchCanvas.height = tRows * 256
  const sCtx = stitchCanvas.getContext('2d')!

  let loadedCount = 0
  const loadTile = (tx: number, ty: number, cx: number, cy: number) =>
    new Promise<void>((resolve) => {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      const timer = window.setTimeout(() => resolve(), 2200)
      img.onload = () => {
        window.clearTimeout(timer)
        sCtx.drawImage(img, cx * 256, cy * 256, 256, 256)
        loadedCount++
        resolve()
      }
      img.onerror = () => {
        window.clearTimeout(timer)
        resolve()
      }
      img.src = `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${zoom}/${ty}/${tx}`
    })

  const tasks: Promise<void>[] = []
  for (let ty = ty0; ty <= ty1; ty++) {
    for (let tx = tx0; tx <= tx1; tx++) {
      tasks.push(loadTile(tx, ty, tx - tx0, ty - ty0))
    }
  }
  await Promise.all(tasks)

  if (loadedCount === tCols * tRows && loadedCount > 0) {
    const cropX = (xMinF - tx0) * 256
    const cropY = (yMinF - ty0) * 256
    const cropW = Math.max(32, (xMaxF - xMinF) * 256)
    const cropH = Math.max(32, (yMaxF - yMinF) * 256)
    oCtx.drawImage(
      stitchCanvas,
      cropX,
      cropY,
      cropW,
      cropH,
      0,
      0,
      outCanvas.width,
      outCanvas.height,
    )
  }
  return outCanvas
}

export function TerrainDiorama3D({
  field,
  mesh,
  overlayMode,
  exaggeration,
  rainIntensityFactor,
  showBoundary,
  showContours,
  isPlayingRain,
  onPointInspect,
}: Props) {
  const mountRef = useRef<HTMLDivElement | null>(null)
  const [textureReady, setTextureReady] = useState<boolean>(false)
  const satCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const inspectRef = useRef(onPointInspect)
  inspectRef.current = onPointInspect

  // Descargar textura satelital real cada vez que cambia la malla del lote
  useEffect(() => {
    let cancelled = false
    if (!mesh || mesh.lon.length === 0 || mesh.lat.length === 0) {
      satCanvasRef.current = null
      setTextureReady(false)
      return
    }
    const west = Math.min(...mesh.lon)
    const east = Math.max(...mesh.lon)
    const south = Math.min(...mesh.lat)
    const north = Math.max(...mesh.lat)

    setTextureReady(false)
    buildSatelliteCanvasTexture(mesh, west, south, east, north).then((canvas) => {
      if (cancelled) return
      satCanvasRef.current = canvas
      setTextureReady(true)
    })
    return () => {
      cancelled = true
    }
  }, [field?.id, mesh?.rows, mesh?.cols])

  useEffect(() => {
    const container = mountRef.current
    if (!container || !mesh || mesh.z_min === null || mesh.z_max === null)
      return

    const { rows, cols, z, in_field } = mesh
    if (rows < 3 || cols < 3) return

    const widthPx = container.clientWidth || 800
    const heightPx = container.clientHeight || 560

    const scene = new THREE.Scene()

    const camera = new THREE.PerspectiveCamera(
      36,
      widthPx / heightPx,
      0.1,
      2000,
    )
    camera.position.set(-34, -122, 74)
    camera.up.set(0, 0, 1)

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    })
    renderer.setSize(widthPx, heightPx)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    container.innerHTML = ''
    container.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.06
    controls.maxPolarAngle = Math.PI * 0.47
    controls.minDistance = 45
    controls.maxDistance = 320
    controls.target.set(0, 0, 4)
    controls.update()

    // Iluminación natural tipo sol de media mañana para resaltar lomas y vaguadas
    const hemi = new THREE.HemisphereLight(0xffffff, 0x8d7b68, 0.85)
    scene.add(hemi)
    const dirLight = new THREE.DirectionalLight(0xfff9ed, 1.15)
    dirLight.position.set(-90, -110, 140)
    scene.add(dirLight)

    // Escalar el bloque 3D a una maqueta normalizada de ~110 unidades de ancho máximo
    const physW = (cols - 1) * mesh.mesh_cell_size_m
    const physH = (rows - 1) * mesh.mesh_cell_size_m
    const maxPhys = Math.max(1, physW, physH)
    const modelSpan = 108.0
    const scaleXY = modelSpan / maxPhys
    const boxW = physW * scaleXY
    const boxH = physH * scaleXY

    const zMin = mesh.z_min
    const zMax = mesh.z_max
    const zSpan = Math.max(1.0, zMax - zMin)
    // Escala vertical de la maqueta: si el lote es de llanura (ej. 22 m en 2 km), damos un realce base
    // digno de maqueta 3D multiplicado por el selector de exageración del usuario
    const baseReliefUnits = Math.max(15.0, Math.min(32.0, zSpan * scaleXY * 4.5))
    const zToUnits = (zv: number | null) => {
      const val = zv === null ? zMin : zv
      return ((val - zMin) / zSpan) * baseReliefUnits * (exaggeration / 2.0)
    }

    // Grilla z en unidades del modelo para interpolación rápida de partículas de agua
    const zGridUnits = new Float32Array(rows * cols)
    for (let i = 0; i < rows * cols; i++) {
      zGridUnits[i] = zToUnits(z[i])
    }

    const sampleZUnits = (uNorm: number, vNorm: number): number => {
      const cf = Math.min(cols - 1.001, Math.max(0, uNorm * (cols - 1)))
      const rf = Math.min(rows - 1.001, Math.max(0, vNorm * (rows - 1)))
      const c0 = Math.floor(cf)
      const r0 = Math.floor(rf)
      const fc = cf - c0
      const fr = rf - r0
      const i00 = r0 * cols + c0
      const z00 = zGridUnits[i00]
      const z10 = zGridUnits[i00 + 1]
      const z01 = zGridUnits[i00 + cols]
      const z11 = zGridUnits[i00 + cols + 1]
      return (
        z00 * (1 - fc) * (1 - fr) +
        z10 * fc * (1 - fr) +
        z01 * (1 - fc) * fr +
        z11 * fc * fr
      )
    }

    const dioramaGroup = new THREE.Group()
    scene.add(dioramaGroup)

    // 1. Construir geometría de la superficie del terreno con UV y colores temáticos opcionales
    const nVerts = rows * cols
    const positions = new Float32Array(nVerts * 3)
    const uvs = new Float32Array(nVerts * 2)
    const colors = new Float32Array(nVerts * 3)

    const wdArr = mesh.water_depth_m
    const lossArr = mesh.soil_loss_t_ha
    const zoneArr = mesh.agronomic_zone_id
    const ndviArr = mesh.ndvi
    const mfdArr = mesh.mfd_area_ha

    for (let r = 0; r < rows; r++) {
      const vNorm = r / (rows - 1)
      const yPos = (0.5 - vNorm) * boxH
      for (let c = 0; c < cols; c++) {
        const uNorm = c / (cols - 1)
        const xPos = (uNorm - 0.5) * boxW
        const idx = r * cols + c
        const zPos = zGridUnits[idx]

        positions[3 * idx] = xPos
        positions[3 * idx + 1] = yPos
        positions[3 * idx + 2] = zPos

        uvs[2 * idx] = uNorm
        uvs[2 * idx + 1] = 1.0 - vNorm

        // Color de tinte según el modo elegido por el agrónomo
        let cr = 1.0
        let cg = 1.0
        let cb = 1.0
        const inside = in_field[idx]

        if (overlayMode === 'waterlogging') {
          const wd = wdArr?.[idx] ?? 0
          const mfd = mfdArr?.[idx] ?? 0
          const wetness = Math.min(1, wd * 4.5 + Math.log10(1 + mfd) * 0.35)
          if (wetness > 0.22) {
            cr = 1.0 - 0.65 * wetness
            cg = 1.0 - 0.15 * wetness
            cb = 1.0 + 0.15 * wetness
          }
        } else if (overlayMode === 'erosion') {
          const loss = lossArr?.[idx] ?? 0
          const u = Math.min(1, loss / 2.2)
          if (u > 0.1) {
            cr = 1.0 + 0.25 * u
            cg = 1.0 - 0.55 * u
            cb = 1.0 - 0.75 * u
          }
        } else if (overlayMode === 'environments') {
          const zid = zoneArr?.[idx] ?? 2
          if (zid === 1) {
            cr = 1.15
            cg = 1.02
            cb = 0.68
          } else if (zid === 2) {
            cr = 0.78
            cg = 1.12
            cb = 0.82
          } else if (zid === 3) {
            cr = 1.25
            cg = 0.76
            cb = 0.45
          } else if (zid === 4) {
            cr = 0.55
            cg = 0.88
            cb = 1.28
          }
        } else if (overlayMode === 'ndvi') {
          const nv = ndviArr?.[idx] ?? 0.5
          const u = Math.min(1, Math.max(0, (nv - 0.25) / 0.5))
          cr = 1.15 - 0.55 * u
          cg = 0.72 + 0.45 * u
          cb = 0.65 - 0.25 * u
        }

        if (!inside) {
          // Atenuar suavemente el área vecina fuera del lote para que el lote resalte
          cr *= 0.88
          cg *= 0.88
          cb *= 0.88
        }

        colors[3 * idx] = cr
        colors[3 * idx + 1] = cg
        colors[3 * idx + 2] = cb
      }
    }

    const indices: number[] = []
    for (let r = 0; r < rows - 1; r++) {
      for (let c = 0; c < cols - 1; c++) {
        const i00 = r * cols + c
        const i01 = i00 + 1
        const i10 = (r + 1) * cols + c
        const i11 = i10 + 1
        indices.push(i00, i10, i01, i01, i10, i11)
      }
    }

    const surfaceGeom = new THREE.BufferGeometry()
    surfaceGeom.setAttribute(
      'position',
      new THREE.BufferAttribute(positions, 3),
    )
    surfaceGeom.setAttribute('uv', new THREE.BufferAttribute(uvs, 2))
    surfaceGeom.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    surfaceGeom.setIndex(indices)
    surfaceGeom.computeVertexNormals()

    let satTexture: THREE.CanvasTexture | null = null
    if (satCanvasRef.current) {
      satTexture = new THREE.CanvasTexture(satCanvasRef.current)
      satTexture.colorSpace = THREE.SRGBColorSpace
      satTexture.anisotropy = 4
    }

    const surfaceMat = new THREE.MeshStandardMaterial({
      map: satTexture,
      vertexColors: true,
      roughness: 0.78,
      metalness: 0.05,
      side: THREE.DoubleSide,
    })
    const terrainMesh = new THREE.Mesh(surfaceGeom, surfaceMat)
    dioramaGroup.add(terrainMesh)

    // 2. Construir el faldón / pedestal lateral de corte geológico (como la maqueta del Caso #1327)
    const baseZ = -4.2
    const skirtPositions: number[] = []
    const pushQuad = (
      x1: number,
      y1: number,
      z1: number,
      x2: number,
      y2: number,
      z2: number,
    ) => {
      skirtPositions.push(
        x1,
        y1,
        z1,
        x1,
        y1,
        baseZ,
        x2,
        y2,
        z2,
        x2,
        y2,
        z2,
        x1,
        y1,
        baseZ,
        x2,
        y2,
        baseZ,
      )
    }
    // Borde norte (r = 0) y borde sur (r = rows - 1)
    for (let c = 0; c < cols - 1; c++) {
      const iN1 = c
      const iN2 = c + 1
      pushQuad(
        positions[3 * iN2],
        positions[3 * iN2 + 1],
        positions[3 * iN2 + 2],
        positions[3 * iN1],
        positions[3 * iN1 + 1],
        positions[3 * iN1 + 2],
      )
      const iS1 = (rows - 1) * cols + c
      const iS2 = iS1 + 1
      pushQuad(
        positions[3 * iS1],
        positions[3 * iS1 + 1],
        positions[3 * iS1 + 2],
        positions[3 * iS2],
        positions[3 * iS2 + 1],
        positions[3 * iS2 + 2],
      )
    }
    // Borde oeste (c = 0) y borde este (c = cols - 1)
    for (let r = 0; r < rows - 1; r++) {
      const iW1 = r * cols
      const iW2 = (r + 1) * cols
      pushQuad(
        positions[3 * iW1],
        positions[3 * iW1 + 1],
        positions[3 * iW1 + 2],
        positions[3 * iW2],
        positions[3 * iW2 + 1],
        positions[3 * iW2 + 2],
      )
      const iE1 = r * cols + (cols - 1)
      const iE2 = (r + 1) * cols + (cols - 1)
      pushQuad(
        positions[3 * iE2],
        positions[3 * iE2 + 1],
        positions[3 * iE2 + 2],
        positions[3 * iE1],
        positions[3 * iE1 + 1],
        positions[3 * iE1 + 2],
      )
    }
    const skirtGeom = new THREE.BufferGeometry()
    skirtGeom.setAttribute(
      'position',
      new THREE.Float32BufferAttribute(skirtPositions, 3),
    )
    skirtGeom.computeVertexNormals()
    const skirtMat = new THREE.MeshStandardMaterial({
      color: 0x574c3f,
      roughness: 0.92,
      side: THREE.DoubleSide,
    })
    dioramaGroup.add(new THREE.Mesh(skirtGeom, skirtMat))

    // 3. Perímetro del lote sobre el relieve (si está activado)
    const west = Math.min(...mesh.lon)
    const east = Math.max(...mesh.lon)
    const south = Math.min(...mesh.lat)
    const north = Math.max(...mesh.lat)
    const lonSpan = Math.max(1e-6, east - west)
    const latSpan = Math.max(1e-6, north - south)

    if (showBoundary && mesh.boundary.length > 0) {
      for (const ring of mesh.boundary) {
        const pts: THREE.Vector3[] = []
        for (const [lo, la, zv] of ring) {
          if (lo === null || la === null) continue
          const uN = (lo - west) / lonSpan
          const vN = (north - la) / latSpan
          const xP = (uN - 0.5) * boxW
          const yP = (0.5 - vN) * boxH
          const zP = zToUnits(zv) + 0.45
          pts.push(new THREE.Vector3(xP, yP, zP))
        }
        if (pts.length >= 2) {
          const bGeom = new THREE.BufferGeometry().setFromPoints(pts)
          const bMat = new THREE.LineBasicMaterial({
            color: 0xfacc15,
            transparent: true,
            opacity: 0.85,
          })
          dioramaGroup.add(new THREE.Line(bGeom, bMat))
        }
      }
    }

    // 4. Venas / cauces de escurrimiento celestes permanentes donde converge el flujo MFD
    if (mfdArr) {
      // Dibujar pequeños trazos celestes en las celdas de concentración para que las vías de agua
      // se vean nítidas sobre la imagen satelital, tal como en la imagen de referencia
      const streamSegs: number[] = []
      const d8Code = mesh.d8_code
      const deltaMap: Record<number, [number, number]> = {
        1: [0, 1],
        2: [1, 1],
        4: [1, 0],
        8: [1, -1],
        16: [0, -1],
        32: [-1, -1],
        64: [-1, 0],
        128: [-1, 1],
      }
      for (let r = 1; r < rows - 1; r++) {
        for (let c = 1; c < cols - 1; c++) {
          const idx = r * cols + c
          const areaHa = mfdArr[idx] ?? 0
          if (areaHa < 1.35) continue
          const code = d8Code?.[idx] ?? 0
          const d = deltaMap[code]
          if (!d) continue
          const nr = r + d[0]
          const nc = c + d[1]
          if (nr < 0 || nr >= rows || nc < 0 || nc >= cols) continue
          const nIdx = nr * cols + nc
          streamSegs.push(
            positions[3 * idx],
            positions[3 * idx + 1],
            positions[3 * idx + 2] + 0.22,
            positions[3 * nIdx],
            positions[3 * nIdx + 1],
            positions[3 * nIdx + 2] + 0.22,
          )
        }
      }
      if (streamSegs.length > 0) {
        const sGeom = new THREE.BufferGeometry()
        sGeom.setAttribute(
          'position',
          new THREE.Float32BufferAttribute(streamSegs, 3),
        )
        const sMat = new THREE.LineBasicMaterial({
          color: 0x00e5ff,
          transparent: true,
          opacity: Math.min(0.95, 0.45 + 0.4 * rainIntensityFactor),
        })
        dioramaGroup.add(new THREE.LineSegments(sGeom, sMat))
      }
    }

    // 5. Sistema físico de gotas/estelas de agua celestes escurriendo por las pendientes del relieve 3D
    const numDrops = Math.round(820 * Math.max(0.25, rainIntensityFactor))
    const dropU = new Float32Array(numDrops)
    const dropV = new Float32Array(numDrops)
    const dropPrevU = new Float32Array(numDrops)
    const dropPrevV = new Float32Array(numDrops)
    const dropAge = new Float32Array(numDrops)
    const dropMaxAge = new Float32Array(numDrops)

    const respawnDrop = (i: number) => {
      // Sembrar gotas en todo el terreno para que escurran hacia las vaguadas y arroyos
      const u = 0.03 + Math.random() * 0.94
      const v = 0.03 + Math.random() * 0.94
      dropU[i] = u
      dropV[i] = v
      dropPrevU[i] = u
      dropPrevV[i] = v
      dropAge[i] = Math.random() * 30
      dropMaxAge[i] = 75 + Math.random() * 110
    }
    for (let i = 0; i < numDrops; i++) respawnDrop(i)

    // Cada gota se dibuja como una pequeña estela (segmento de línea entre posición previa y actual)
    // y una cabeza brillante, creando el efecto idéntico a la simulación de lluvia del Caso #1327
    const streakPositions = new Float32Array(numDrops * 6)
    const headPositions = new Float32Array(numDrops * 3)

    const streakGeom = new THREE.BufferGeometry()
    streakGeom.setAttribute(
      'position',
      new THREE.BufferAttribute(streakPositions, 3),
    )
    const streakMat = new THREE.LineBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.88,
    })
    const streakLines = new THREE.LineSegments(streakGeom, streakMat)
    dioramaGroup.add(streakLines)

    const headGeom = new THREE.BufferGeometry()
    headGeom.setAttribute(
      'position',
      new THREE.BufferAttribute(headPositions, 3),
    )
    const headMat = new THREE.PointsMaterial({
      color: 0x67e8f9,
      size: 2.1,
      transparent: true,
      opacity: 0.92,
      sizeAttenuation: false,
    })
    const headPoints = new THREE.Points(headGeom, headMat)
    dioramaGroup.add(headPoints)

    // Precalcular gradiente descendente (du, dv) en cada celda de la malla
    const gradU = new Float32Array(rows * cols)
    const gradV = new Float32Array(rows * cols)
    for (let r = 1; r < rows - 1; r++) {
      for (let c = 1; c < cols - 1; c++) {
        const idx = r * cols + c
        const dzdc = (zGridUnits[idx + 1] - zGridUnits[idx - 1]) * 0.5
        const dzdr = (zGridUnits[idx + cols] - zGridUnits[idx - cols]) * 0.5
        // Descenso: opuesto al gradiente
        let gu = -dzdc
        let gv = -dzdr
        const mag = Math.hypot(gu, gv)
        if (mag > 1e-4) {
          // Velocidad proporcional a sqrt(pendiente), acotada para movimiento suave
          const speed = Math.min(0.0065, 0.0014 + 0.0042 * Math.sqrt(mag))
          gu = (gu / mag) * speed
          gv = (gv / mag) * speed
        } else {
          // Si está en una celda casi plana, buscar la vecina D8 más baja
          let bestDrop = 0
          let bestDr = 0
          let bestDc = 0
          for (let dr = -1; dr <= 1; dr++) {
            for (let dc = -1; dc <= 1; dc++) {
              if (dr === 0 && dc === 0) continue
              const diff = zGridUnits[idx] - zGridUnits[(r + dr) * cols + (c + dc)]
              if (diff > bestDrop) {
                bestDrop = diff
                bestDr = dr
                bestDc = dc
              }
            }
          }
          gu = bestDc * 0.0012
          gv = bestDr * 0.0012
        }
        gradU[idx] = gu
        gradV[idx] = gv
      }
    }

    // Raycaster para inspeccionar cualquier punto de la maqueta con un clic
    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2()
    let downX = 0
    let downY = 0
    const onPointerDown = (ev: MouseEvent) => {
      downX = ev.clientX
      downY = ev.clientY
    }
    const onPointerUp = (ev: MouseEvent) => {
      if (Math.hypot(ev.clientX - downX, ev.clientY - downY) > 5) return
      if (!inspectRef.current) return
      const rect = renderer.domElement.getBoundingClientRect()
      pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1
      pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1
      raycaster.setFromCamera(pointer, camera)
      const hits = raycaster.intersectObject(terrainMesh, false)
      if (hits.length > 0 && hits[0].uv) {
        const uN = hits[0].uv.x
        const vN = 1.0 - hits[0].uv.y
        const clickedLon = west + uN * lonSpan
        const clickedLat = north - vN * latSpan
        inspectRef.current(
          Number(clickedLon.toFixed(6)),
          Number(clickedLat.toFixed(6)),
        )
      }
    }
    renderer.domElement.addEventListener('mousedown', onPointerDown)
    renderer.domElement.addEventListener('mouseup', onPointerUp)

    let animId: number | null = null
    const animate = () => {
      controls.update()

      if (isPlayingRain && rainIntensityFactor > 0.05) {
        streakLines.visible = true
        headPoints.visible = true
        const sArr = (
          streakGeom.getAttribute('position') as THREE.BufferAttribute
        ).array as Float32Array
        const hArr = (
          headGeom.getAttribute('position') as THREE.BufferAttribute
        ).array as Float32Array

        const speedMult = 0.65 + 0.55 * rainIntensityFactor
        for (let i = 0; i < numDrops; i++) {
          let u = dropU[i]
          let v = dropV[i]
          const c = Math.min(cols - 2, Math.max(1, Math.round(u * (cols - 1))))
          const r = Math.min(rows - 2, Math.max(1, Math.round(v * (rows - 1))))
          const idx = r * cols + c
          const gu = gradU[idx] * speedMult
          const gv = gradV[idx] * speedMult

          dropPrevU[i] = u
          dropPrevV[i] = v
          u += gu
          v += gv
          dropAge[i] += 1

          const stalled = Math.hypot(gu, gv) < 0.00018 && dropAge[i] > 45
          if (
            u <= 0.015 ||
            u >= 0.985 ||
            v <= 0.015 ||
            v >= 0.985 ||
            dropAge[i] >= dropMaxAge[i] ||
            stalled
          ) {
            respawnDrop(i)
            u = dropU[i]
            v = dropV[i]
          } else {
            dropU[i] = u
            dropV[i] = v
          }

          const pu = dropPrevU[i]
          const pv = dropPrevV[i]
          // Estirar ligeramente la cola para que se vea como chorro de agua
          const tailU = u - (u - pu) * 2.8
          const tailV = v - (v - pv) * 2.8

          const xHead = (u - 0.5) * boxW
          const yHead = (0.5 - v) * boxH
          const zHead = sampleZUnits(u, v) + 0.32

          const xTail = (tailU - 0.5) * boxW
          const yTail = (0.5 - tailV) * boxH
          const zTail = sampleZUnits(tailU, tailV) + 0.32

          sArr[6 * i] = xTail
          sArr[6 * i + 1] = yTail
          sArr[6 * i + 2] = zTail
          sArr[6 * i + 3] = xHead
          sArr[6 * i + 4] = yHead
          sArr[6 * i + 5] = zHead

          hArr[3 * i] = xHead
          hArr[3 * i + 1] = yHead
          hArr[3 * i + 2] = zHead
        }
        ;(
          streakGeom.getAttribute('position') as THREE.BufferAttribute
        ).needsUpdate = true
        ;(
          headGeom.getAttribute('position') as THREE.BufferAttribute
        ).needsUpdate = true
      } else {
        streakLines.visible = false
        headPoints.visible = false
      }

      renderer.render(scene, camera)
      animId = window.requestAnimationFrame(animate)
    }
    animId = window.requestAnimationFrame(animate)

    const onResize = () => {
      if (!container) return
      const w = container.clientWidth || 800
      const h = container.clientHeight || 560
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    window.addEventListener('resize', onResize)

    return () => {
      if (animId !== null) window.cancelAnimationFrame(animId)
      window.removeEventListener('resize', onResize)
      renderer.domElement.removeEventListener('mousedown', onPointerDown)
      renderer.domElement.removeEventListener('mouseup', onPointerUp)
      controls.dispose()
      surfaceGeom.dispose()
      surfaceMat.dispose()
      satTexture?.dispose()
      skirtGeom.dispose()
      skirtMat.dispose()
      streakGeom.dispose()
      streakMat.dispose()
      headGeom.dispose()
      headMat.dispose()
      renderer.dispose()
    }
  }, [
    mesh,
    textureReady,
    overlayMode,
    exaggeration,
    rainIntensityFactor,
    showBoundary,
    showContours,
    isPlayingRain,
  ])

  return (
    <div className="diorama-wrapper">
      <div ref={mountRef} className="diorama-canvas" />
      <div className="diorama-hint">
        🖱️ Arrastrá con botón izquierdo para rotar la maqueta 3D · Rueda para
        zoom · Clic sobre el lote para consultar cota y pendiente
      </div>
    </div>
  )
}
