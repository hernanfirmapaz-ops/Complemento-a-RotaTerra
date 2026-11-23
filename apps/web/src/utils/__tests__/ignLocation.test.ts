import { describe, it, expect } from 'vitest'
import {
  computeBoundingBox,
  isPointInRing,
  isPointInGeometry,
  resolveLocationFromBoundaries,
  BoundariesCache,
} from '../ignLocation'

describe('ignLocation - Punto en polígono y resolución de ubicación IGN (Issue #84)', () => {
  const squareRing = [
    [-66.0, -34.0],
    [-65.0, -34.0],
    [-65.0, -33.0],
    [-66.0, -33.0],
    [-66.0, -34.0],
  ]

  it('determina correctamente si un punto está dentro o fuera de un anillo', () => {
    // Centro del cuadrado
    expect(isPointInRing([-65.5, -33.5], squareRing)).toBe(true)
    // Fuera del cuadrado
    expect(isPointInRing([-64.0, -33.5], squareRing)).toBe(false)
    expect(isPointInRing([-65.5, -35.0], squareRing)).toBe(false)
  })

  it('calcula bounding box y descarta puntos exteriores en O(1)', () => {
    const bbox = computeBoundingBox(squareRing)
    expect(bbox).toEqual([-66.0, -34.0, -65.0, -33.0])

    const geom = { type: 'Polygon', coordinates: [squareRing] }
    expect(isPointInGeometry([-65.5, -33.5], geom, bbox)).toBe(true)
    expect(isPointInGeometry([-70.0, -33.5], geom, bbox)).toBe(false)
  })

  it('maneja geometrías con huecos (holes)', () => {
    const holeRing = [
      [-65.6, -33.6],
      [-65.4, -33.6],
      [-65.4, -33.4],
      [-65.6, -33.4],
      [-65.6, -33.6],
    ]
    const geomWithHole = {
      type: 'Polygon',
      coordinates: [squareRing, holeRing],
    }

    // Punto dentro del anillo exterior pero fuera del hueco
    expect(isPointInGeometry([-65.8, -33.8], geomWithHole)).toBe(true)
    // Punto dentro del hueco interior: debe dar false
    expect(isPointInGeometry([-65.5, -33.5], geomWithHole)).toBe(false)
  })

  it('soporta geometrías MultiPolygon', () => {
    const multiGeom = {
      type: 'MultiPolygon',
      coordinates: [
        [squareRing],
        [
          [
            [-60.0, -32.0],
            [-59.0, -32.0],
            [-59.0, -31.0],
            [-60.0, -31.0],
            [-60.0, -32.0],
          ],
        ],
      ],
    }
    expect(isPointInGeometry([-65.5, -33.5], multiGeom)).toBe(true)
    expect(isPointInGeometry([-59.5, -31.5], multiGeom)).toBe(true)
    expect(isPointInGeometry([-62.0, -32.5], multiGeom)).toBe(false)
  })

  it('resuelve ubicación según el nivel de zoom (<6, 6-7, >=7)', () => {
    const boundaries: BoundariesCache = {
      provincias: [
        {
          type: 'Feature',
          properties: { nombre: 'San Luis', in1: '74' },
          geometry: { type: 'Polygon', coordinates: [squareRing] },
          bbox: [-66.0, -34.0, -65.0, -33.0],
        },
      ],
      departamentos: [
        {
          type: 'Feature',
          properties: {
            nombre: 'Juan Martín de Pueyrredón',
            provincia: 'San Luis',
            in1: '74056',
          },
          geometry: { type: 'Polygon', coordinates: [squareRing] },
          bbox: [-66.0, -34.0, -65.0, -33.0],
        },
      ],
    }

    const lon = -65.5
    const lat = -33.5

    // Zoom < 6: solo país "Argentina"
    expect(resolveLocationFromBoundaries(lon, lat, 4, boundaries)).toBe('Argentina')
    expect(resolveLocationFromBoundaries(lon, lat, 5.9, boundaries)).toBe('Argentina')

    // Zoom 6 a 7: solo provincia
    expect(resolveLocationFromBoundaries(lon, lat, 6.0, boundaries)).toBe('San Luis')
    expect(resolveLocationFromBoundaries(lon, lat, 6.8, boundaries)).toBe('San Luis')

    // Zoom >= 7: Provincia · Departamento
    expect(resolveLocationFromBoundaries(lon, lat, 7.0, boundaries)).toBe(
      'San Luis · Juan Martín de Pueyrredón',
    )
    expect(resolveLocationFromBoundaries(lon, lat, 14.0, boundaries)).toBe(
      'San Luis · Juan Martín de Pueyrredón',
    )

    // Punto fuera de Argentina: null
    expect(resolveLocationFromBoundaries(10.0, 50.0, 10, boundaries)).toBeNull()
  })
})
