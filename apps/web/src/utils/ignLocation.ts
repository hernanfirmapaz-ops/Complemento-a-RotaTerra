/**
 * Utilidades de geolocalización local basadas en los límites vectoriales oficiales del IGN.
 *
 * Permite resolver la ubicación (Argentina / Provincia / Departamento) de forma 100% local
 * mediante algoritmos de punto en polígono (ray-casting), sin latencia de red ni consultas
 * a servidores externos o backend (Issue #84).
 */

export interface BoundaryFeature {
  type: string
  properties: {
    nombre: string
    provincia?: string
    in1?: string
    [key: string]: any
  }
  geometry: {
    type: string
    coordinates: any
  }
  bbox?: [number, number, number, number]
}

export interface BoundariesCache {
  provincias?: BoundaryFeature[]
  departamentos?: BoundaryFeature[]
}

/**
 * Calcula el bounding box [minLon, minLat, maxLon, maxLat] de una geometría GeoJSON.
 */
export function computeBoundingBox(coords: any): [number, number, number, number] {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity

  function traverse(c: any) {
    if (typeof c[0] === 'number') {
      const x = c[0]
      const y = c[1]
      if (x < minX) minX = x
      if (x > maxX) maxX = x
      if (y < minY) minY = y
      if (y > maxY) maxY = y
    } else {
      for (let i = 0; i < c.length; i++) {
        traverse(c[i])
      }
    }
  }

  traverse(coords)
  return [minX, minY, maxX, maxY]
}

/**
 * Prepara las features agregando su bounding box en memoria para consultas O(1) de pre-filtrado.
 */
export function prepareBoundaryFeatures(features: any[]): BoundaryFeature[] {
  return features.map((f) => ({
    ...f,
    bbox: computeBoundingBox(f.geometry?.coordinates ?? []),
  }))
}

/**
 * Verifica si un punto [lon, lat] se encuentra dentro de un anillo de coordenadas.
 * Algoritmo de cruce de rayos (Ray-Casting / Jordan Curve Theorem).
 */
export function isPointInRing(point: [number, number], ring: number[][]): boolean {
  const [x, y] = point
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0]
    const yi = ring[i][1]
    const xj = ring[j][0]
    const yj = ring[j][1]
    const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi
    if (intersect) inside = !inside
  }
  return inside
}

/**
 * Verifica si un punto [lon, lat] está dentro de una geometría Polygon o MultiPolygon.
 */
export function isPointInGeometry(
  point: [number, number],
  geometry: { type: string; coordinates: any },
  bbox?: [number, number, number, number],
): boolean {
  const [x, y] = point
  if (bbox) {
    if (x < bbox[0] || x > bbox[2] || y < bbox[1] || y > bbox[3]) {
      return false
    }
  }

  if (geometry.type === 'Polygon') {
    const rings = geometry.coordinates as number[][][]
    if (!rings || rings.length === 0) return false
    if (!isPointInRing(point, rings[0])) return false
    for (let i = 1; i < rings.length; i++) {
      if (isPointInRing(point, rings[i])) return false
    }
    return true
  }

  if (geometry.type === 'MultiPolygon') {
    const polys = geometry.coordinates as number[][][][]
    if (!polys) return false
    for (const polyRings of polys) {
      if (!polyRings || polyRings.length === 0) continue
      if (isPointInRing(point, polyRings[0])) {
        let inHole = false
        for (let i = 1; i < polyRings.length; i++) {
          if (isPointInRing(point, polyRings[i])) {
            inHole = true
            break
          }
        }
        if (!inHole) return true
      }
    }
    return false
  }

  return false
}

/**
 * Determina el texto oficial de la ficha de ubicación IGN según coordenadas y nivel de zoom:
 * - Zoom < 6: vacía o "Argentina".
 * - Zoom 6 a 7: solo provincia (ej. "San Luis").
 * - Zoom >= 7: "Provincia · Departamento" (ej. "San Luis · Juan Martín de Pueyrredón").
 * Si el punto está fuera de la República Argentina, retorna null.
 */
export function resolveLocationFromBoundaries(
  lon: number,
  lat: number,
  zoom: number,
  boundaries: BoundariesCache,
): string | null {
  const pt: [number, number] = [lon, lat]
  const provs = boundaries.provincias || []
  const deptos = boundaries.departamentos || []

  // 1. Buscar provincia que contenga el punto
  let matchedProv: BoundaryFeature | null = null
  for (const f of provs) {
    if (isPointInGeometry(pt, f.geometry, f.bbox)) {
      matchedProv = f
      break
    }
  }

  // 2. Si el zoom lo requiere (o si no se halló provincia), buscar departamento
  let matchedDepto: BoundaryFeature | null = null
  if (zoom >= 7 || !matchedProv) {
    for (const f of deptos) {
      if (isPointInGeometry(pt, f.geometry, f.bbox)) {
        matchedDepto = f
        break
      }
    }
  }

  // Si no coincide con ninguna entidad argentina, el punto está fuera del país
  if (!matchedProv && !matchedDepto) {
    return null
  }

  const provName = matchedProv?.properties?.nombre || matchedDepto?.properties?.provincia

  // Regla por nivel de zoom (Issue #84):
  if (zoom < 6) {
    return 'Argentina'
  }

  if (zoom >= 6 && zoom < 7) {
    return provName || 'Argentina'
  }

  // Zoom >= 7: Provincia · Departamento
  if (matchedDepto) {
    const dName = matchedDepto.properties.nombre
    const pName = matchedDepto.properties.provincia || provName
    return pName ? `${pName} · ${dName}` : dName
  }

  return provName || 'Argentina'
}
