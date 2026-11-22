import * as THREE from 'three'

/**
 * Spec 013 - Etapa 1: Malla propia de agua 4x y bordes suaves con corte en umbral físico.
 */

/**
 * Constantes visuales de presentación (Spec 013):
 * Escalan la lámina sobre la exageración vertical del terreno y evitan z-fighting
 * con el relieve subyacente. No alteran el valor físico de profundidad h.
 */
export const WATER_SURFACE_ELEVATION_EXAGGERATION_SCALE = 0.35
export const WATER_SURFACE_Z_BIAS = 0.04

export interface CreateWaterGeometryOptions {
  positions: Float32Array | number[]
  waterDepthArr: Float32Array | number[]
  rows: number
  cols: number
  exaggeration: number
  subdivision?: number
  zBias?: number
}

export interface CreateWaterMaterialOptions {
  pondingThresholdM: number
  rainIntensityFactor?: number
  waterColor?: number
}

/**
 * Interpolación bilineal de 4 puntos vecinos según Spec 013, sección 3:
 * h(u, v) = (1-u)(1-v)h00 + u(1-v)h10 + (1-u)v h01 + uv h11
 */
export function interpolateBilinear(
  v00: number,
  v10: number,
  v01: number,
  v11: number,
  u: number,
  v: number,
): number {
  const w00 = (1.0 - u) * (1.0 - v)
  const w10 = u * (1.0 - v)
  const w01 = (1.0 - u) * v
  const w11 = u * v
  return w00 * v00 + w10 * v10 + w01 * v01 + w11 * v11
}

/**
 * Factor de desvanecimiento suave de opacidad según Spec 013:
 * - Si h < h_umbral: 0 (en el shader se hace discard)
 * - Si h >= h_umbral: smoothstep(h_umbral, 1.5 * h_umbral, h)
 */
export function computeWaterOpacityFactor(h: number, hUmbral: number): number {
  if (h < hUmbral) return 0.0
  const hMax = 1.5 * hUmbral
  if (h >= hMax) return 1.0
  const t = Math.max(0.0, Math.min(1.0, (h - hUmbral) / (hMax - hUmbral)))
  return t * t * (3.0 - 2.0 * t)
}

/**
 * Genera una BufferGeometry desacoplada para el espejo de agua con sobremuestreo bilineal 4x.
 */
export function createWaterGeometry4x({
  positions,
  waterDepthArr,
  rows,
  cols,
  exaggeration,
  subdivision = 4,
  zBias = WATER_SURFACE_Z_BIAS,
}: CreateWaterGeometryOptions): THREE.BufferGeometry {
  const geom = new THREE.BufferGeometry()
  const N = Math.max(1, Math.round(subdivision))

  const waterPositions: number[] = []
  const waterDepths: number[] = []
  const waterUVs: number[] = []
  const waterIndices: number[] = []

  let vertCount = 0

  for (let r = 0; r < rows - 1; r++) {
    for (let c = 0; c < cols - 1; c++) {
      const i00 = r * cols + c
      const i10 = i00 + 1
      const i01 = i00 + cols
      const i11 = i01 + 1

      const d00 = waterDepthArr[i00] ?? 0
      const d10 = waterDepthArr[i10] ?? 0
      const d01 = waterDepthArr[i01] ?? 0
      const d11 = waterDepthArr[i11] ?? 0

      // Si ninguna esquina tiene lámina de agua positiva, omitir celda
      if (d00 <= 0 && d10 <= 0 && d01 <= 0 && d11 <= 0) {
        continue
      }

      const p00x = positions[3 * i00]
      const p00y = positions[3 * i00 + 1]
      const p00z = positions[3 * i00 + 2]

      const p10x = positions[3 * i10]
      const p10y = positions[3 * i10 + 1]
      const p10z = positions[3 * i10 + 2]

      const p01x = positions[3 * i01]
      const p01y = positions[3 * i01 + 1]
      const p01z = positions[3 * i01 + 2]

      const p11x = positions[3 * i11]
      const p11y = positions[3 * i11 + 1]
      const p11z = positions[3 * i11 + 2]

      // Subdividir la celda en N x N subcuadros con interpolación bilineal
      for (let sr = 0; sr < N; sr++) {
        for (let sc = 0; sc < N; sc++) {
          const uA = sc / N
          const uB = (sc + 1) / N
          const vA = sr / N
          const vB = (sr + 1) / N

          // 4 esquinas del subcuadro: (uA, vA), (uB, vA), (uA, vB), (uB, vB)
          const subCorners = [
            { u: uA, v: vA, cOffset: uA, rOffset: vA },
            { u: uB, v: vA, cOffset: uB, rOffset: vA },
            { u: uA, v: vB, cOffset: uA, rOffset: vB },
            { u: uB, v: vB, cOffset: uB, rOffset: vB },
          ]

          const startIdx = vertCount

          for (const pt of subCorners) {
            const x = interpolateBilinear(p00x, p10x, p01x, p11x, pt.u, pt.v)
            const y = interpolateBilinear(p00y, p10y, p01y, p11y, pt.u, pt.v)
            const zTerr = interpolateBilinear(p00z, p10z, p01z, p11z, pt.u, pt.v)
            const h = interpolateBilinear(d00, d10, d01, d11, pt.u, pt.v)

            // Elevación libre del espejo de agua: constante visual para evitar oclusión/z-fighting
            const eta =
              zTerr +
              Math.max(0.0, h) * (exaggeration / 2.0) * WATER_SURFACE_ELEVATION_EXAGGERATION_SCALE +
              zBias

            waterPositions.push(x, y, eta)
            waterDepths.push(h)
            waterUVs.push((c + pt.cOffset) / (cols - 1), 1.0 - (r + pt.rOffset) / (rows - 1))
          }

          // Dos triángulos por subcuadro:
          // 0 = (uA, vA), 1 = (uB, vA), 2 = (uA, vB), 3 = (uB, vB)
          waterIndices.push(
            startIdx, startIdx + 2, startIdx + 1,
            startIdx + 1, startIdx + 2, startIdx + 3,
          )

          vertCount += 4
        }
      }
    }
  }

  if (waterPositions.length > 0) {
    geom.setAttribute('position', new THREE.Float32BufferAttribute(waterPositions, 3))
    geom.setAttribute('waterDepth', new THREE.Float32BufferAttribute(waterDepths, 1))
    geom.setAttribute('uv', new THREE.Float32BufferAttribute(waterUVs, 2))
    geom.setIndex(waterIndices)
    geom.computeVertexNormals()
  }

  return geom
}

/**
 * ShaderMaterial para agua fluida con desvanecimiento suave y corte estricto según Spec 013.
 */
export function createWaterShaderMaterial({
  pondingThresholdM,
  rainIntensityFactor = 1.0,
  waterColor = 0x0284c7,
}: CreateWaterMaterialOptions): THREE.ShaderMaterial {
  const uniforms = {
    uTime: { value: 0.0 },
    uPondingThreshold: { value: pondingThresholdM },
    uWaterColor: { value: new THREE.Color(waterColor) },
    uOpacity: { value: Math.min(0.92, 0.70 + 0.20 * rainIntensityFactor) },
  }

  const vertexShader = `
    attribute float waterDepth;
    varying float vWaterDepth;
    varying vec3 vNormal;
    varying vec3 vViewPosition;
    varying vec2 vUv;
    uniform float uTime;

    void main() {
      vWaterDepth = waterDepth;
      vUv = uv;
      vNormal = normalize(normalMatrix * normal);

      // Ondulación sutil calculada en GPU sin costo en CPU
      float wave = sin(position.x * 0.28 + uTime * 3.5) * cos(position.y * 0.24 - uTime * 2.8) * 0.05;
      vec3 displacedPos = position + vec3(0.0, 0.0, wave);

      vec4 mvPosition = modelViewMatrix * vec4(displacedPos, 1.0);
      vViewPosition = -mvPosition.xyz;
      gl_Position = projectionMatrix * mvPosition;
    }
  `

  const fragmentShader = `
    uniform float uPondingThreshold;
    uniform vec3 uWaterColor;
    uniform float uOpacity;
    varying float vWaterDepth;
    varying vec3 vNormal;
    varying vec3 vViewPosition;
    varying vec2 vUv;

    void main() {
      // Corte estricto en el umbral físico del motor (si h < h_umbral, no se dibuja agua)
      if (vWaterDepth < uPondingThreshold) {
        discard;
      }

      // Desvanecimiento suave: smoothstep(h_umbral, 1.5 * h_umbral, h)
      float alphaFactor = smoothstep(uPondingThreshold, 1.5 * uPondingThreshold, vWaterDepth);
      float alpha = uOpacity * alphaFactor;

      // Sombreado direccional solar suave
      vec3 lightDir = normalize(vec3(0.45, 0.75, 0.65));
      vec3 normal = normalize(vNormal);
      float diff = max(dot(normal, lightDir), 0.0);
      vec3 viewDir = normalize(vViewPosition);
      vec3 halfDir = normalize(lightDir + viewDir);
      float spec = pow(max(dot(normal, halfDir), 0.0), 32.0);

      vec3 finalColor = uWaterColor * (0.65 + 0.35 * diff) + vec3(spec * 0.28);
      gl_FragColor = vec4(finalColor, alpha);
    }
  `

  return new THREE.ShaderMaterial({
    uniforms,
    vertexShader,
    fragmentShader,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
  })
}
