import * as THREE from 'three'
import { describe, it, expect } from 'vitest'
import {
  isRainAutoShutoff,
  computeActiveDropCount,
  computeSplashRadius,
  computeSplashOpacity,
  createCircleSpriteTexture,
  RainSimulationSystem,
  RAIN_MAX_PARTICLES,
  SPLASH_DURATION_SEC,
  RAIN_INTENSITY_MIN_NORMALIZED,
  RAIN_INTENSITY_MAX_NORMALIZED,
  RAIN_DROPLET_BASE_OPACITY,
  RAIN_DROP_BASE_SPEED,
  RAIN_DROP_SPEED_VARIATION,
} from '../RainSimulation'

describe('Spec 013 - Etapa 5: Lluvia ligera y realista (Sprites 2-4 px, Salpicaduras y Apagado)', () => {
  it('expone constantes visuales calibradas con nombre para lluvia y salpicaduras', () => {
    expect(RAIN_INTENSITY_MIN_NORMALIZED).toBe(0.1)
    expect(RAIN_INTENSITY_MAX_NORMALIZED).toBe(2.0)
    expect(RAIN_DROPLET_BASE_OPACITY).toBe(0.85)
    expect(RAIN_DROP_BASE_SPEED).toBe(1.35)
    expect(RAIN_DROP_SPEED_VARIATION).toBe(0.85)
  })

  it('determina el apagado automático cuando se detiene el evento o la intensidad cae a cero', () => {
    expect(isRainAutoShutoff(0.0, true)).toBe(true)
    expect(isRainAutoShutoff(0.0005, true)).toBe(true)
    expect(isRainAutoShutoff(1.0, false)).toBe(true)
    expect(isRainAutoShutoff(1.0, true)).toBe(false)
  })

  it('modula la densidad de gotas según la intensidad de lluvia con tope estricto para 60 FPS', () => {
    expect(RAIN_MAX_PARTICLES).toBe(1800)
    expect(computeActiveDropCount(0.0)).toBe(0)
    // Con intensidad 1.0 (50% de 2.0): mitad del tope
    const half = computeActiveDropCount(1.0, 1000)
    expect(half).toBe(500)
    // Con intensidad 2.0 (máxima): tope completo
    const full = computeActiveDropCount(2.0, 1000)
    expect(full).toBe(1000)
    // Con intensidad mayor a 2.0: respeta el tope máximo
    expect(computeActiveDropCount(3.5, 1000)).toBe(1000)
  })

  it('calcula la expansión y desvanecimiento de las salpicaduras al impacto en ~0.3 s', () => {
    expect(SPLASH_DURATION_SEC).toBeCloseTo(0.3)

    // Radio inicial y final
    const rStart = computeSplashRadius(0.0)
    const rEnd = computeSplashRadius(1.0)
    expect(rStart).toBeCloseTo(0.12)
    expect(rEnd).toBeGreaterThan(1.0)
    expect(rEnd).toBeLessThan(1.5)

    // Opacidad de desvanecimiento
    expect(computeSplashOpacity(0.0)).toBe(1.0)
    expect(computeSplashOpacity(0.5)).toBeCloseTo(0.5)
    expect(computeSplashOpacity(1.0)).toBe(0.0)
  })

  it('crea la textura de sprite circular suave sin lanzar excepciones', () => {
    const tex = createCircleSpriteTexture()
    expect(tex).toBeDefined()
  })

  it('instancia y actualiza el sistema de simulación de lluvia y salpicaduras', () => {
    const system = new RainSimulationSystem({
      boxW: 100,
      boxH: 100,
      sampleZUnits: (_u, _v) => 10.0,
      maxParticles: 500,
    })

    const pointsMesh = system.getPointsMesh()
    const splashMesh = system.getSplashMesh()

    expect(pointsMesh.type).toBe('Points')
    const mat = pointsMesh.material as THREE.PointsMaterial
    expect(mat.transparent).toBe(true)
    expect(mat.size).toBeGreaterThanOrEqual(2.0)
    expect(mat.size).toBeLessThanOrEqual(4.0)

    // 1. Simulación activa: mallas visibles y partículas actualizadas
    system.update(0.016, 1.0, true)
    expect(pointsMesh.visible).toBe(true)
    expect(splashMesh.visible).toBe(true)

    // 2. Apagado automático al pausar o terminar evento: mallas ocultas
    system.update(0.016, 0.0, false)
    expect(pointsMesh.visible).toBe(false)
    expect(splashMesh.visible).toBe(false)

    // Limpieza
    system.dispose()
  })

  it('desactiva las salpicaduras automáticamente en el Modo Liviano', () => {
    const system = new RainSimulationSystem({
      boxW: 100,
      boxH: 100,
      sampleZUnits: () => 5.0,
      isLiteMode: true,
    })

    system.update(0.016, 1.2, true)
    expect(system.getPointsMesh().visible).toBe(true)
    expect(system.getSplashMesh().visible).toBe(false)

    system.dispose()
  })
})
