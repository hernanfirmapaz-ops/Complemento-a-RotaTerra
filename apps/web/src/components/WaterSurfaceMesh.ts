import * as THREE from 'three'

/**
 * Spec 013: Malla de agua 4x, bordes suaves, Fresnel y Flow Map.
 *
 * Regla de datos: Los cortes de color son parámetros visuales calibrables,
 * no datos físicos del modelo agronómico.
 */

/**
 * Constantes visuales de presentación (Spec 013):
 * Escalan la lámina sobre la exageración vertical del terreno y evitan z-fighting
 * con el relieve subyacente. No alteran el valor físico de profundidad h.
 */
export const WATER_SURFACE_ELEVATION_EXAGGERATION_SCALE = 0.35
export const WATER_SURFACE_Z_BIAS = 0.04

export const WATER_VISUAL_SHALLOW_DEPTH_M = 0.08 // Corte de agua somera: 8 cm
export const WATER_VISUAL_DEEP_DEPTH_M = 0.25 // Corte de agua profunda: 25 cm

export const WATER_COLOR_SHALLOW = new THREE.Color(82 / 255, 185 / 255, 195 / 255) // Turquesa claro traslúcido
export const WATER_COLOR_MEDIUM = new THREE.Color(35 / 255, 120 / 255, 175 / 255) // Azul cerceta medio
export const WATER_COLOR_DEEP = new THREE.Color(15 / 255, 60 / 255, 120 / 255) // Azul ultramar profundo

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
  enableFlowMap?: boolean
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
 * Aproximación de Fresnel según Schlick (1994):
 * R(theta) = R0 + (1 - R0) * (1 - cos(theta))^5
 *
 * Derivación física para agua (interfaz aire-agua):
 * Con índice de refracción del aire n1 = 1.0 y del agua n2 ≈ 1.333:
 * R0 = ((n1 - n2) / (n1 + n2))^2 = ((1.0 - 1.333) / (1.0 + 1.333))^2 = (-0.333 / 2.333)^2 ≈ 0.0204 ≈ 0.02
 *
 * Referencia bibliográfica:
 * Schlick, Christophe (1994). "An Inexpensive BRDF Model for Physically-Based Rendering".
 * Computer Graphics Forum, 13(3): 233–246. DOI: 10.1111/1467-8659.1330233
 */
export function computeFresnel(cosTheta: number, R0 = 0.02): number {
  const c = Math.max(0.0, Math.min(1.0, cosTheta))
  return R0 + (1.0 - R0) * Math.pow(1.0 - c, 5)
}

/**
 * Obtiene el color base del gradiente batimétrico según los parámetros visuales de profundidad.
 */
export function getWaterDepthColor(h: number): THREE.Color {
  if (h < WATER_VISUAL_SHALLOW_DEPTH_M) {
    return WATER_COLOR_SHALLOW.clone()
  }
  if (h <= WATER_VISUAL_DEEP_DEPTH_M) {
    const t = (h - WATER_VISUAL_SHALLOW_DEPTH_M) / (WATER_VISUAL_DEEP_DEPTH_M - WATER_VISUAL_SHALLOW_DEPTH_M)
    return new THREE.Color().lerpColors(
      WATER_COLOR_SHALLOW,
      WATER_COLOR_MEDIUM,
      Math.max(0.0, Math.min(1.0, t)),
    )
  }
  return WATER_COLOR_DEEP.clone()
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
 * ShaderMaterial para agua fluida con Fresnel, Flow Map de Vlachos y gradiente batimétrico (Spec 013).
 */
export function createWaterShaderMaterial({
  pondingThresholdM,
  rainIntensityFactor = 1.0,
  waterColor: _waterColor,
  enableFlowMap = true,
}: CreateWaterMaterialOptions): THREE.ShaderMaterial {
  const uniforms = {
    uTime: { value: 0.0 },
    uPondingThreshold: { value: pondingThresholdM },
    uVisualShallowDepth: { value: WATER_VISUAL_SHALLOW_DEPTH_M },
    uVisualDeepDepth: { value: WATER_VISUAL_DEEP_DEPTH_M },
    uColorShallow: { value: WATER_COLOR_SHALLOW.clone() },
    uColorMedium: { value: WATER_COLOR_MEDIUM.clone() },
    uColorDeep: { value: WATER_COLOR_DEEP.clone() },
    uSkyColor: { value: new THREE.Color(0xdbeafe) },
    uOpacity: { value: Math.min(0.94, 0.72 + 0.20 * rainIntensityFactor) },
    uEnableFlowMap: { value: enableFlowMap ? 1.0 : 0.0 },
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
      float wave = sin(position.x * 0.28 + uTime * 2.8) * cos(position.y * 0.24 - uTime * 2.1) * 0.05;
      vec3 displacedPos = position + vec3(0.0, 0.0, wave);

      vec4 mvPosition = modelViewMatrix * vec4(displacedPos, 1.0);
      vViewPosition = -mvPosition.xyz;
      gl_Position = projectionMatrix * mvPosition;
    }
  `

  const fragmentShader = `
    uniform float uPondingThreshold;
    uniform float uVisualShallowDepth;
    uniform float uVisualDeepDepth;
    uniform vec3 uColorShallow;
    uniform vec3 uColorMedium;
    uniform vec3 uColorDeep;
    uniform vec3 uSkyColor;
    uniform float uOpacity;
    uniform float uTime;
    uniform float uEnableFlowMap;

    varying float vWaterDepth;
    varying vec3 vNormal;
    varying vec3 vViewPosition;
    varying vec2 vUv;

    // Generador analítico de perturbación de normales (ondas superficiales)
    vec3 getWaveNormal(vec2 p, float t) {
      float k1 = 28.0; float k2 = 54.0;
      float dX = cos(p.x * k1 + t * 2.5) * 0.08 + cos((p.x + p.y) * k2 + t * 3.4) * 0.04;
      float dY = -sin(p.y * k1 - t * 2.1) * 0.08 + sin((p.x - p.y) * k2 - t * 2.9) * 0.04;
      return normalize(vec3(-dX, -dY, 1.0));
    }

    void main() {
      // 1. Corte estricto en el umbral físico del motor (si h < h_umbral, discard)
      if (vWaterDepth < uPondingThreshold) {
        discard;
      }

      // 2. Desvanecimiento suave en los bordes: smoothstep(h_umbral, 1.5 * h_umbral, h)
      float alphaFactor = smoothstep(uPondingThreshold, 1.5 * uPondingThreshold, vWaterDepth);
      float alpha = uOpacity * alphaFactor;

      // 3. Gradiente cromático por batimetría (parámetros visuales declarados)
      vec3 waterBaseColor;
      if (vWaterDepth < uVisualShallowDepth) {
        float t = clamp(vWaterDepth / uVisualShallowDepth, 0.0, 1.0);
        waterBaseColor = mix(uColorShallow * 1.08, uColorShallow, t);
      } else if (vWaterDepth < uVisualDeepDepth) {
        float t = clamp((vWaterDepth - uVisualShallowDepth) / (uVisualDeepDepth - uVisualShallowDepth), 0.0, 1.0);
        waterBaseColor = mix(uColorShallow, uColorMedium, t);
      } else {
        float t = clamp((vWaterDepth - uVisualDeepDepth) / (uVisualDeepDepth * 1.5), 0.0, 1.0);
        waterBaseColor = mix(uColorMedium, uColorDeep, t);
      }

      // 4. Flow Map de dos fases (Vlachos, Valve SIGGRAPH 2010)
      vec3 waveNormal = vec3(0.0, 0.0, 1.0);
      if (uEnableFlowMap > 0.5) {
        float t1 = fract(uTime * 0.14);
        float t2 = fract(uTime * 0.14 + 0.5);
        float flowWeight = 1.0 - abs(2.0 * t1 - 1.0);
        vec2 flowDir = normalize(vec2(0.55, -0.83));
        vec3 wn1 = getWaveNormal(vUv * 36.0 + flowDir * t1 * 0.75, uTime * 2.2);
        vec3 wn2 = getWaveNormal(vUv * 36.0 + flowDir * t2 * 0.75, uTime * 2.2);
        waveNormal = normalize(mix(wn2, wn1, flowWeight));
      }

      // 5. Normal final perturbada y aproximación de Fresnel de Schlick (1994)
      vec3 normal = normalize(vNormal + waveNormal * 0.24);
      vec3 viewDir = normalize(vViewPosition);
      float cosTheta = clamp(dot(normal, viewDir), 0.0, 1.0);
      float R0 = 0.02; // Coeficiente de reflexión en incidencia normal para agua
      float fresnel = R0 + (1.0 - R0) * pow(1.0 - cosTheta, 5.0);

      // 6. Iluminación solar suave Blinn-Phong + mezcla Fresnel con cielo
      vec3 lightDir = normalize(vec3(0.45, 0.75, 0.65));
      float diff = max(dot(normal, lightDir), 0.0);
      vec3 halfDir = normalize(lightDir + viewDir);
      float spec = pow(max(dot(normal, halfDir), 0.0), 36.0);

      vec3 litWater = waterBaseColor * (0.62 + 0.38 * diff);
      vec3 finalColor = mix(litWater, uSkyColor, fresnel * 0.75) + vec3(spec * 0.32);

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
