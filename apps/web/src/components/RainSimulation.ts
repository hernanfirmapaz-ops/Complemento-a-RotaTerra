import * as THREE from 'three'

/**
 * Spec 013 - Etapa 5: Lluvia ligera y realista con gotas sprite (2–4 px) y salpicaduras.
 *
 * Especificaciones:
 * 1. Gotas en sprites redondos (THREE.Points con textura circular tenue), descartando líneas alargadas.
 * 2. Tamaño visual adaptativo de 2 a 4 px según distancia o escala.
 * 3. Salpicaduras al impacto: anillo concéntrico fino que se expande y desvanece en ~0.3 s.
 * 4. Densidad sincronizada con la tasa de precipitación (mm/h / factor de intensidad).
 * 5. Apagado automático al finalizar el evento de lluvia sin intervención del usuario.
 */

export const RAIN_MAX_PARTICLES = 1800
export const RAIN_MAX_SPLASHES = 90
export const SPLASH_DURATION_SEC = 0.30 // ~300 ms de desvanecimiento
export const SPLASH_SEGMENTS_COUNT = 10

/**
 * Constantes visuales de simulación de lluvia (Spec 013 - Etapa 5):
 * Calibradas para realismo visual sin sobrecargar el visor 3D ni obstruir el relieve.
 */
export const RAIN_INTENSITY_MIN_NORMALIZED = 0.1
export const RAIN_INTENSITY_MAX_NORMALIZED = 2.0
export const RAIN_DROPLET_BASE_OPACITY = 0.85
export const RAIN_DROP_BASE_SPEED = 1.35
export const RAIN_DROP_SPEED_VARIATION = 0.85

/**
 * Verifica si la lluvia debe apagarse automáticamente.
 */
export function isRainAutoShutoff(intensityFactor: number, isPlaying: boolean): boolean {
  return !isPlaying || intensityFactor <= 0.001
}

/**
 * Calcula la cantidad de gotas activas según el factor de intensidad de lluvia (Tope estricto para 60 FPS).
 */
export function computeActiveDropCount(
  intensityFactor: number,
  maxParticles = RAIN_MAX_PARTICLES,
): number {
  if (intensityFactor <= 0.001) return 0
  const normalized = Math.max(
    RAIN_INTENSITY_MIN_NORMALIZED,
    Math.min(RAIN_INTENSITY_MAX_NORMALIZED, intensityFactor),
  )
  return Math.min(
    maxParticles,
    Math.round(maxParticles * (normalized / RAIN_INTENSITY_MAX_NORMALIZED)),
  )
}

/**
 * Calcula el radio expandido de la salpicadura al impacto en función del progreso [0..1].
 */
export function computeSplashRadius(
  progress: number,
  startRadius = 0.12,
  maxRadius = 1.15,
): number {
  const p = Math.max(0.0, Math.min(1.0, progress))
  // Expansión rápida inicial y desaceleración suave (ease-out cuadrático)
  const easeOut = 1.0 - (1.0 - p) * (1.0 - p)
  return startRadius + (maxRadius - startRadius) * easeOut
}

/**
 * Calcula la opacidad del anillo de salpicadura en función del progreso [0..1] para desvanecerse en ~0.3 s.
 */
export function computeSplashOpacity(progress: number): number {
  const p = Math.max(0.0, Math.min(1.0, progress))
  // Desvanecimiento suave hacia 0
  return Math.max(0.0, 1.0 - p)
}

/**
 * Genera la textura de sprite circular suave (punto con brillo tenue y desvanecimiento radial).
 */
export function createCircleSpriteTexture(): THREE.Texture {
  if (typeof document !== 'undefined') {
    try {
      const canvas = document.createElement('canvas')
      canvas.width = 64
      canvas.height = 64
      const ctx = canvas.getContext ? canvas.getContext('2d') : null
      if (ctx) {
        const cx = 32
        const cy = 32
        const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 30)
        // Centro brillante tenue, desvanecimiento exterior suave
        grad.addColorStop(0.0, 'rgba(255, 255, 255, 0.95)')
        grad.addColorStop(0.35, 'rgba(186, 230, 253, 0.70)')
        grad.addColorStop(0.70, 'rgba(125, 211, 252, 0.30)')
        grad.addColorStop(1.0, 'rgba(125, 211, 252, 0.0)')
        ctx.fillStyle = grad
        ctx.beginPath()
        ctx.arc(cx, cy, 30, 0, Math.PI * 2)
        ctx.fill()

        const texture = new THREE.CanvasTexture(canvas)
        texture.minFilter = THREE.LinearFilter
        texture.magFilter = THREE.LinearFilter
        texture.generateMipmaps = false
        return texture
      }
    } catch {
      // Fallback a DataTexture si el entorno de prueba no soporta getContext('2d')
    }
  }

  // Generación matemática de gradiente radial como DataTexture
  const size = 32
  const data = new Uint8Array(size * size * 4)
  const center = size / 2
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = (y * size + x) * 4
      const dist = Math.hypot(x - center, y - center) / center
      if (dist <= 1.0) {
        const alpha = Math.floor(255 * Math.max(0.0, 1.0 - dist * dist))
        data[idx] = 224 // #e0
        data[idx + 1] = 242 // #f2
        data[idx + 2] = 254 // #fe
        data[idx + 3] = alpha
      } else {
        data[idx + 3] = 0
      }
    }
  }
  const tex = new THREE.DataTexture(data, size, size, THREE.RGBAFormat)
  tex.needsUpdate = true
  return tex
}

export interface RainSimulationOptions {
  boxW: number
  boxH: number
  sampleZUnits: (u: number, v: number) => number
  maxParticles?: number
  isLiteMode?: boolean
}

/**
 * Controlador de simulación de lluvia ligera y salpicaduras conformes a la Spec 013 (Etapa 5).
 */
export class RainSimulationSystem {
  private boxW: number
  private boxH: number
  private sampleZUnits: (u: number, v: number) => number
  private isLiteMode: boolean
  private maxParticles: number

  // Partículas de lluvia (THREE.Points)
  private rainPosX: Float32Array
  private rainPosY: Float32Array
  private rainPosZ: Float32Array
  private rainSpeed: Float32Array
  private pointsPositions: Float32Array
  private pointsGeom: THREE.BufferGeometry
  private pointsMat: THREE.PointsMaterial
  private pointsMesh: THREE.Points
  private spriteTexture: THREE.Texture

  // Salpicaduras (anillos concéntricos finos en THREE.LineSegments)
  private splashX: Float32Array
  private splashY: Float32Array
  private splashZ: Float32Array
  private splashAge: Float32Array
  private splashActive: Uint8Array
  private nextSplashIdx = 0
  private splashPositions: Float32Array
  private splashGeom: THREE.BufferGeometry
  private splashMat: THREE.LineBasicMaterial
  private splashMesh: THREE.LineSegments

  constructor(options: RainSimulationOptions) {
    this.boxW = options.boxW
    this.boxH = options.boxH
    this.sampleZUnits = options.sampleZUnits
    this.isLiteMode = options.isLiteMode ?? false
    this.maxParticles = options.maxParticles ?? RAIN_MAX_PARTICLES

    // 1. Inicializar buffers de gotas
    this.rainPosX = new Float32Array(this.maxParticles)
    this.rainPosY = new Float32Array(this.maxParticles)
    this.rainPosZ = new Float32Array(this.maxParticles)
    this.rainSpeed = new Float32Array(this.maxParticles)
    this.pointsPositions = new Float32Array(this.maxParticles * 3)

    for (let i = 0; i < this.maxParticles; i++) {
      this.respawnDrop(i, true)
      this.pointsPositions[3 * i] = this.rainPosX[i]
      this.pointsPositions[3 * i + 1] = this.rainPosY[i]
      this.pointsPositions[3 * i + 2] = this.rainPosZ[i]
    }

    this.pointsGeom = new THREE.BufferGeometry()
    this.pointsGeom.setAttribute(
      'position',
      new THREE.BufferAttribute(this.pointsPositions, 3),
    )

    this.spriteTexture = createCircleSpriteTexture()
    this.pointsMat = new THREE.PointsMaterial({
      map: this.spriteTexture,
      color: 0xe0f2fe,
      size: 2.8, // Tamaño adaptativo de 2 a 4 px
      sizeAttenuation: true,
      transparent: true,
      opacity: RAIN_DROPLET_BASE_OPACITY,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    this.pointsMesh = new THREE.Points(this.pointsGeom, this.pointsMat)

    // 2. Inicializar buffers de salpicaduras
    this.splashX = new Float32Array(RAIN_MAX_SPLASHES)
    this.splashY = new Float32Array(RAIN_MAX_SPLASHES)
    this.splashZ = new Float32Array(RAIN_MAX_SPLASHES)
    this.splashAge = new Float32Array(RAIN_MAX_SPLASHES)
    this.splashActive = new Uint8Array(RAIN_MAX_SPLASHES)
    this.splashPositions = new Float32Array(RAIN_MAX_SPLASHES * SPLASH_SEGMENTS_COUNT * 6)

    this.splashGeom = new THREE.BufferGeometry()
    this.splashGeom.setAttribute(
      'position',
      new THREE.BufferAttribute(this.splashPositions, 3),
    )
    this.splashMat = new THREE.LineBasicMaterial({
      color: 0x7dd3fc,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    this.splashMesh = new THREE.LineSegments(this.splashGeom, this.splashMat)
  }

  private respawnDrop(k: number, initHigh = false): void {
    const u = Math.random()
    const v = Math.random()
    this.rainPosX[k] = (u - 0.5) * this.boxW
    this.rainPosY[k] = (0.5 - v) * this.boxH
    const gz = this.sampleZUnits(u, v)
    this.rainPosZ[k] = initHigh
      ? gz + 5 + Math.random() * 45
      : gz + 35 + Math.random() * 20
    this.rainSpeed[k] =
      RAIN_DROP_BASE_SPEED + Math.random() * RAIN_DROP_SPEED_VARIATION
  }

  private triggerSplash(sx: number, sy: number, sz: number): void {
    if (this.isLiteMode) return // Desactivado automáticamente en modo liviano
    const idx = this.nextSplashIdx
    this.nextSplashIdx = (this.nextSplashIdx + 1) % RAIN_MAX_SPLASHES
    this.splashX[idx] = sx
    this.splashY[idx] = sy
    this.splashZ[idx] = sz + 0.08
    this.splashAge[idx] = 0
    this.splashActive[idx] = 1
  }

  /**
   * Actualiza la simulación en cada cuadro.
   * Garantiza apagado automático e impacto con salpicaduras en ~0.3 s.
   */
  public update(dtSeconds: number, rainIntensityFactor: number, isPlaying: boolean): void {
    const autoShutoff = isRainAutoShutoff(rainIntensityFactor, isPlaying)

    if (autoShutoff) {
      // Ocultar mallas cuando no hay lluvia activa
      this.pointsMesh.visible = false
      this.splashMesh.visible = false
      return
    }

    this.pointsMesh.visible = true
    this.splashMesh.visible = !this.isLiteMode

    const targetParticles = computeActiveDropCount(rainIntensityFactor, this.maxParticles)
    const posAttr = this.pointsGeom.getAttribute('position') as THREE.BufferAttribute
    const posArray = posAttr.array as Float32Array

    // Deriva suave natural de viento (ligero ángulo, estiramiento nulo)
    const driftX = -0.06
    const driftY = -0.04

    for (let k = 0; k < this.maxParticles; k++) {
      if (k >= targetParticles) {
        // Fuera de la densidad actual: esconder bajo tierra
        posArray[3 * k + 2] = -9999.0
        continue
      }

      const uNorm = this.rainPosX[k] / this.boxW + 0.5
      const vNorm = 0.5 - this.rainPosY[k] / this.boxH
      const groundZ =
        uNorm >= 0 && uNorm <= 1 && vNorm >= 0 && vNorm <= 1
          ? this.sampleZUnits(uNorm, vNorm)
          : 0

      // Caída según velocidad y dt
      const speedFactor = 60.0 * Math.max(0.008, Math.min(0.032, dtSeconds))
      this.rainPosZ[k] -= this.rainSpeed[k] * speedFactor
      this.rainPosX[k] += driftX * speedFactor
      this.rainPosY[k] += driftY * speedFactor

      if (this.rainPosZ[k] <= groundZ) {
        // Impacto contra el suelo / superficie de agua
        this.triggerSplash(this.rainPosX[k], this.rainPosY[k], groundZ)
        this.respawnDrop(k, false)
      }

      posArray[3 * k] = this.rainPosX[k]
      posArray[3 * k + 1] = this.rainPosY[k]
      posArray[3 * k + 2] = this.rainPosZ[k]
    }
    posAttr.needsUpdate = true

    // Actualizar salpicaduras
    if (!this.isLiteMode) {
      const sPosAttr = this.splashGeom.getAttribute('position') as THREE.BufferAttribute
      const sPosArray = sPosAttr.array as Float32Array

      for (let k = 0; k < RAIN_MAX_SPLASHES; k++) {
        if (!this.splashActive[k]) {
          for (let seg = 0; seg < SPLASH_SEGMENTS_COUNT * 6; seg++) {
            sPosArray[k * SPLASH_SEGMENTS_COUNT * 6 + seg] = 0
          }
          continue
        }

        this.splashAge[k] += dtSeconds
        const progress = this.splashAge[k] / SPLASH_DURATION_SEC

        if (progress >= 1.0) {
          this.splashActive[k] = 0
          for (let seg = 0; seg < SPLASH_SEGMENTS_COUNT * 6; seg++) {
            sPosArray[k * SPLASH_SEGMENTS_COUNT * 6 + seg] = 0
          }
          continue
        }

        const radius = computeSplashRadius(progress)
        const cx = this.splashX[k]
        const cy = this.splashY[k]
        const cz = this.splashZ[k]

        for (let seg = 0; seg < SPLASH_SEGMENTS_COUNT; seg++) {
          const a1 = (seg / SPLASH_SEGMENTS_COUNT) * Math.PI * 2
          const a2 = ((seg + 1) / SPLASH_SEGMENTS_COUNT) * Math.PI * 2
          const baseIdx = k * SPLASH_SEGMENTS_COUNT * 6 + seg * 6

          sPosArray[baseIdx] = cx + Math.cos(a1) * radius
          sPosArray[baseIdx + 1] = cy + Math.sin(a1) * radius
          sPosArray[baseIdx + 2] = cz
          sPosArray[baseIdx + 3] = cx + Math.cos(a2) * radius
          sPosArray[baseIdx + 4] = cy + Math.sin(a2) * radius
          sPosArray[baseIdx + 5] = cz
        }
      }
      sPosAttr.needsUpdate = true
    }
  }

  public getPointsMesh(): THREE.Points {
    return this.pointsMesh
  }

  public getSplashMesh(): THREE.LineSegments {
    return this.splashMesh
  }

  public dispose(): void {
    this.pointsGeom.dispose()
    this.pointsMat.dispose()
    this.spriteTexture.dispose()
    this.splashGeom.dispose()
    this.splashMat.dispose()
  }
}
