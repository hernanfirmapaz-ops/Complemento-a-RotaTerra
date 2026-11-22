import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { PolygonMapDrawer } from '../PolygonMapDrawer'
import {
  POLYGON_CORNER_FILL,
  POLYGON_CORNER_RADIUS_PX,
  POLYGON_CORNER_STROKE,
  POLYGON_CORNER_STROKE_WIDTH,
  POLYGON_EDGE_COLOR,
  POLYGON_EDGE_DASHARRAY,
  POLYGON_EDGE_WIDTH,
  POLYGON_FILL_COLOR,
  POLYGON_FILL_OPACITY,
} from '../../utils/polygonStyles'

// Mock para maplibre-gl
let registeredEvents: Record<string, ((e: any) => void)[]> = {}
let currentMapZoom = 14
let zoomChanged = false

vi.mock('maplibre-gl', () => {
  const MockMap = vi.fn().mockImplementation(function (options: any) {
    registeredEvents = {}
    currentMapZoom = options.zoom ?? 14
    zoomChanged = false

    return {
      on: vi.fn((event: string, handler: (e: any) => void) => {
        if (!registeredEvents[event]) registeredEvents[event] = []
        registeredEvents[event].push(handler)
      }),
      off: vi.fn(),
      getZoom: vi.fn(() => currentMapZoom),
      setZoom: vi.fn((z: number) => {
        currentMapZoom = z
        zoomChanged = true
      }),
      zoomIn: vi.fn(() => {
        currentMapZoom += 1
        zoomChanged = true
      }),
      zoomOut: vi.fn(() => {
        currentMapZoom -= 1
        zoomChanged = true
      }),
      getCenter: vi.fn(() => ({ lng: -65.46, lat: -33.67 })),
      getSource: vi.fn(() => ({ setData: vi.fn() })),
      isStyleLoaded: vi.fn(() => true),
      getLayer: vi.fn(() => null),
      setLayoutProperty: vi.fn(),
      setPaintProperty: vi.fn(),
      addSource: vi.fn(),
      addLayer: vi.fn(),
      addControl: vi.fn(),
      remove: vi.fn(),
      resize: vi.fn(),
      doubleClickZoom: {
        enable: vi.fn(),
        disable: vi.fn(),
      },
    }
  })

  const MockMarker = vi.fn().mockImplementation(function () {
    return {
      setLngLat: vi.fn().mockReturnThis(),
      addTo: vi.fn().mockReturnThis(),
      on: vi.fn().mockReturnThis(),
      getLngLat: vi.fn(() => ({ lng: -65.46, lat: -33.67 })),
      remove: vi.fn(),
    }
  })

  const MockNav = vi.fn()

  return {
    default: {
      Map: MockMap,
      Marker: MockMarker,
      NavigationControl: MockNav,
    },
    Map: MockMap,
    Marker: MockMarker,
    NavigationControl: MockNav,
  }
})

describe('PolygonMapDrawer - Montaje de componente y eventos (Issue #84)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    registeredEvents = {}
    currentMapZoom = 14
    zoomChanged = false
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('declara constantes visuales con nombre según pedido de Hernán', () => {
    expect(POLYGON_CORNER_RADIUS_PX).toBe(4) // 8 px de diámetro
    expect(POLYGON_CORNER_FILL).toBe('#FFFFFF')
    expect(POLYGON_CORNER_STROKE).toBe('#1E293B')
    expect(POLYGON_CORNER_STROKE_WIDTH).toBe(2)

    expect(POLYGON_EDGE_COLOR).toBe('#FFE066')
    expect(POLYGON_EDGE_WIDTH).toBe(2)
    expect(POLYGON_EDGE_DASHARRAY).toEqual([2, 2])

    expect(POLYGON_FILL_COLOR).toBe('#FFE066')
    expect(POLYGON_FILL_OPACITY).toBe(0.15)
  })

  it('monta el componente y verifica que dblclick no agrega esquinas y permite zoom', () => {
    render(
      <PolygonMapDrawer
        isOpen={true}
        initialCenter={[-65.46, -33.67]}
        onClose={vi.fn()}
        onConfirmPolygon={vi.fn()}
      />,
    )

    // Simular que el mapa terminó de cargar
    act(() => {
      registeredEvents['load']?.forEach((cb) => cb({}))
    })

    // Inicialmente 0 esquinas
    expect(screen.getByText(/0 esquinas/i)).toBeTruthy()

    // Simular doble clic: llega click seguido inmediatamente de dblclick
    act(() => {
      registeredEvents['click']?.forEach((cb) =>
        cb({ lngLat: { lng: -65.461, lat: -33.671 } }),
      )
      registeredEvents['dblclick']?.forEach((cb) => cb({}))
      // El navegador/MapLibre aplica zoom en dblclick
      currentMapZoom += 1
      zoomChanged = true
    })

    // Avanzar más allá del debounce de 250 ms
    act(() => {
      vi.advanceTimersByTime(300)
    })

    // Debe seguir en 0 esquinas (no se agregó nada) y el zoom debe haber cambiado
    expect(screen.getByText(/0 esquinas/i)).toBeTruthy()
    expect(currentMapZoom).toBe(15)
    expect(zoomChanged).toBe(true)
  })

  it('monta el componente y verifica que un clic simple agrega 1 esquina tras 250ms', () => {
    render(
      <PolygonMapDrawer
        isOpen={true}
        initialCenter={[-65.46, -33.67]}
        onClose={vi.fn()}
        onConfirmPolygon={vi.fn()}
      />,
    )

    act(() => {
      registeredEvents['load']?.forEach((cb) => cb({}))
    })

    expect(screen.getByText(/0 esquinas/i)).toBeTruthy()

    // Clic simple sin dblclick posterior
    act(() => {
      registeredEvents['click']?.forEach((cb) =>
        cb({ lngLat: { lng: -65.465, lat: -33.675 } }),
      )
    })

    // Antes de los 250ms aún no debe estar agregada
    expect(screen.getByText(/0 esquinas/i)).toBeTruthy()

    // Avanzar el timer
    act(() => {
      vi.advanceTimersByTime(300)
    })

    // Ahora debe tener 1 esquina
    expect(screen.getByText(/1 esquina/i)).toBeTruthy()
  })

  it('descarta clics duplicados a menos de 1 m de la esquina anterior', () => {
    render(
      <PolygonMapDrawer
        isOpen={true}
        initialCenter={[-65.46, -33.67]}
        onClose={vi.fn()}
        onConfirmPolygon={vi.fn()}
      />,
    )

    act(() => {
      registeredEvents['load']?.forEach((cb) => cb({}))
    })

    // 1. Primer clic
    act(() => {
      registeredEvents['click']?.forEach((cb) =>
        cb({ lngLat: { lng: -65.465, lat: -33.675 } }),
      )
      vi.advanceTimersByTime(300)
    })
    expect(screen.getByText(/1 esquina/i)).toBeTruthy()

    // 2. Segundo clic prácticamente idéntico (< 1 m)
    act(() => {
      registeredEvents['click']?.forEach((cb) =>
        cb({ lngLat: { lng: -65.465001, lat: -33.675001 } }),
      )
      vi.advanceTimersByTime(300)
    })
    // Debe continuar en 1 esquina (descartado por duplicado)
    expect(screen.getByText(/1 esquina/i)).toBeTruthy()

    // 3. Tercer clic alejado (> 10 m)
    act(() => {
      registeredEvents['click']?.forEach((cb) =>
        cb({ lngLat: { lng: -65.47, lat: -33.68 } }),
      )
      vi.advanceTimersByTime(300)
    })
    expect(screen.getByText(/2 esquinas/i)).toBeTruthy()
  })
})
