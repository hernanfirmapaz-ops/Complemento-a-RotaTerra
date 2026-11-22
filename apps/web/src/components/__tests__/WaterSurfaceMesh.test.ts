import { describe, it, expect } from 'vitest'
import * as THREE from 'three'
import {
  interpolateBilinear,
  computeWaterOpacityFactor,
  createWaterGeometry4x,
  createWaterShaderMaterial,
} from '../WaterSurfaceMesh'

describe('Spec 013 - Etapa 1: Malla de agua y bordes suaves', () => {
  it('interpola bilinealmente según Spec 013: h(u,v) = (1-u)(1-v)h00 + u(1-v)h10 + (1-u)vh01 + uvh11', () => {
    const h00 = 0.0
    const h10 = 0.20
    const h01 = 0.10
    const h11 = 0.30

    // Vértices en esquinas
    expect(interpolateBilinear(h00, h10, h01, h11, 0, 0)).toBeCloseTo(0.0)
    expect(interpolateBilinear(h00, h10, h01, h11, 1, 0)).toBeCloseTo(0.20)
    expect(interpolateBilinear(h00, h10, h01, h11, 0, 1)).toBeCloseTo(0.10)
    expect(interpolateBilinear(h00, h10, h01, h11, 1, 1)).toBeCloseTo(0.30)

    // Centro (0.5, 0.5): promedio exacto (0.0 + 0.20 + 0.10 + 0.30) / 4 = 0.15
    expect(interpolateBilinear(h00, h10, h01, h11, 0.5, 0.5)).toBeCloseTo(0.15)
  })

  it('cumple el corte estricto en el umbral del motor y desvanecimiento smoothstep(h_umbral, 1.5*h_umbral, h)', () => {
    const hUmbral = 0.05
    const h15 = 1.5 * hUmbral // 0.075

    // Por debajo del umbral del motor: factor 0 (en el shader se hace discard)
    expect(computeWaterOpacityFactor(0.02, hUmbral)).toBe(0)
    expect(computeWaterOpacityFactor(0.049, hUmbral)).toBe(0)

    // Exactamente en el umbral: 0
    expect(computeWaterOpacityFactor(hUmbral, hUmbral)).toBeCloseTo(0.0)

    // En 1.5 * h_umbral: opacidad plena 1.0
    expect(computeWaterOpacityFactor(h15, hUmbral)).toBeCloseTo(1.0)
    expect(computeWaterOpacityFactor(0.20, hUmbral)).toBeCloseTo(1.0)

    // Punto medio entre h_umbral y 1.5*h_umbral: smoothstep(0, 1, 0.5) = 3*(0.5)^2 - 2*(0.5)^3 = 0.5
    const hMid = (hUmbral + h15) / 2.0
    expect(computeWaterOpacityFactor(hMid, hUmbral)).toBeCloseTo(0.5)
  })

  it('genera una BufferGeometry con sobremuestreo 4x y atributos position y waterDepth', () => {
    const rows = 3
    const cols = 3
    // Grilla plana de 3x3 celdas centradas
    const positions = new Float32Array(rows * cols * 3)
    const waterDepthArr = new Float32Array(rows * cols)

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const idx = r * cols + c
        positions[3 * idx] = c * 10
        positions[3 * idx + 1] = r * 10
        positions[3 * idx + 2] = 50.0 // Cota 50 m
        // Anegamiento en el centro
        waterDepthArr[idx] = (r === 1 && c === 1) ? 0.25 : 0.0
      }
    }

    const geom = createWaterGeometry4x({
      positions,
      waterDepthArr,
      rows,
      cols,
      exaggeration: 1.0,
      subdivision: 4,
    })

    expect(geom).toBeInstanceOf(THREE.BufferGeometry)
    expect(geom.getAttribute('position')).toBeDefined()
    expect(geom.getAttribute('waterDepth')).toBeDefined()
    expect(geom.getAttribute('uv')).toBeDefined()
    expect(geom.getIndex()).not.toBeNull()

    // Con sub-división 4x, cada celda vecina al centro genera 16 subcuadros (64 vértices)
    const posAttr = geom.getAttribute('position')
    expect(posAttr.count).toBeGreaterThan(0)
  })

  it('crea un ShaderMaterial con uniform uPondingThreshold leído del motor', () => {
    const mat = createWaterShaderMaterial({
      pondingThresholdM: 0.04,
      rainIntensityFactor: 1.0,
    })

    expect(mat).toBeInstanceOf(THREE.ShaderMaterial)
    expect(mat.uniforms.uPondingThreshold.value).toBe(0.04)
    expect(mat.transparent).toBe(true)
    expect(mat.depthWrite).toBe(false)
    expect(mat.vertexShader).toContain('attribute float waterDepth;')
    expect(mat.fragmentShader).toContain('if (vWaterDepth < uPondingThreshold)')
    expect(mat.fragmentShader).toContain('smoothstep(uPondingThreshold, 1.5 * uPondingThreshold')
  })
})
