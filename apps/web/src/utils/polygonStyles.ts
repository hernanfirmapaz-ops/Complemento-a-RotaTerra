/** Constantes visuales con nombre y utilidades geométricas para delimitación de lote y límites IGN (Issue #84). */

// 1. Estilo del polígono delimitador de lote (Pedido de Hernán, Issue #84)
export const POLYGON_CORNER_RADIUS_PX = 4 // ~8 px de diámetro total
export const POLYGON_CORNER_FILL = '#FFFFFF'
export const POLYGON_CORNER_STROKE = '#1E293B' // Borde oscuro de alto contraste
export const POLYGON_CORNER_STROKE_WIDTH = 2
export const POLYGON_EDGE_COLOR = '#FFE066' // Línea de alto contraste sobre satélite
export const POLYGON_EDGE_WIDTH = 2 // ~2 px
export const POLYGON_EDGE_DASHARRAY = [2, 2] // Línea punteada
export const POLYGON_FILL_COLOR = '#FFE066' // Amarillo muy tenue
export const POLYGON_FILL_OPACITY = 0.15 // Opacidad ~0.15 que deja ver el mapa debajo

// 2. Estilo de los límites oficiales del IGN (Vectoriales estáticos, Issue #84)
export const IGN_LINE_COLOR = '#FFFFFF'

// Provincias: ancho ~2px, opacidad ~0.9, visible desde zoom 3
export const IGN_PROVINCIA_WIDTH = 2
export const IGN_PROVINCIA_OPACITY = 0.9
export const IGN_PROVINCIA_MINZOOM = 3
export const IGN_PROVINCIA_OPACITY_EXPR: any = [
  'interpolate',
  ['linear'],
  ['zoom'],
  2.5,
  0,
  3.5,
  IGN_PROVINCIA_OPACITY,
]

// Departamentos: ancho ~1px, opacidad ~0.6, visible desde zoom ~7 (minzoom con fade)
export const IGN_DEPARTAMENTO_WIDTH = 1
export const IGN_DEPARTAMENTO_OPACITY = 0.6
export const IGN_DEPARTAMENTO_MINZOOM = 6.5
export const IGN_DEPARTAMENTO_OPACITY_EXPR: any = [
  'interpolate',
  ['linear'],
  ['zoom'],
  6.5,
  0,
  7.5,
  IGN_DEPARTAMENTO_OPACITY,
]

/** Calcula la distancia en metros entre dos coordenadas [lon, lat] usando proyección equirectangular local. */
export function computeDistanceM(p1: [number, number], p2: [number, number]): number {
  const latMeanRad = ((p1[1] + p2[1]) / 2) * (Math.PI / 180)
  const dx = (p2[0] - p1[0]) * 111319.488 * Math.cos(latMeanRad)
  const dy = (p2[1] - p1[1]) * 111132.954
  return Math.hypot(dx, dy)
}
