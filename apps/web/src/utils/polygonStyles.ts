/** Constantes visuales con nombre y utilidades geométricas para delimitación de lote (Pedido de Hernán, Issue #84). */

export const POLYGON_CORNER_RADIUS_PX = 4 // ~8 px de diámetro total
export const POLYGON_CORNER_FILL = '#FFFFFF'
export const POLYGON_CORNER_STROKE = '#1E293B' // Borde oscuro de alto contraste
export const POLYGON_CORNER_STROKE_WIDTH = 2
export const POLYGON_EDGE_COLOR = '#FFE066' // Línea de alto contraste sobre satélite
export const POLYGON_EDGE_WIDTH = 2 // ~2 px
export const POLYGON_EDGE_DASHARRAY = [2, 2] // Línea punteada
export const POLYGON_FILL_COLOR = '#FFE066' // Amarillo muy tenue
export const POLYGON_FILL_OPACITY = 0.15 // Opacidad ~0.15 que deja ver el mapa debajo

/** Calcula la distancia en metros entre dos coordenadas [lon, lat] usando proyección equirectangular local. */
export function computeDistanceM(p1: [number, number], p2: [number, number]): number {
  const latMeanRad = ((p1[1] + p2[1]) / 2) * (Math.PI / 180)
  const dx = (p2[0] - p1[0]) * 111319.488 * Math.cos(latMeanRad)
  const dy = (p2[1] - p1[1]) * 111132.954
  return Math.hypot(dx, dy)
}
