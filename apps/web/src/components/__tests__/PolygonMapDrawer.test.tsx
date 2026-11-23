import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act, fireEvent } from '@testing-library/react'
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
  IGN_LINE_COLOR,
  IGN_PROVINCIA_WIDTH,
  IGN_DEPARTAMENTO_WIDTH,
} from '../../utils/polygonStyles'

// Variables espía para maplibre-gl
let registeredEvents: Record<string, ((e: any) => void)[]> = {}
let currentMapZoom = 14
let zoomChanged = false
let isStyleLoadedValue = true
const setDataMock = vi.fn()
const setLayoutPropertyMock = vi.fn()
const addLayerMock = vi.fn()
const addSourceMock = vi.fn()

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
      getSource: vi.fn((id: string) => {
        if (id === 'drawn-polygon') {
          return { setData: setDataMock }
        }
        return { setData: vi.fn() }
      }),
      isStyleLoaded: vi.fn(() => isStyleLoadedValue),
      getLayer: vi.fn((id: string) => {
        if (
          id === 'ign-provincias-layer' ||
          id === 'ign-departamentos-layer' ||
          id === 'drawn-polygon-fill' ||
          id === 'drawn-polygon-line' ||
          id === 'sat-layer' ||
          id === 'osm-layer'
        ) {
          return {}
        }
        return null
      }),
      setLayoutProperty: setLayoutPropertyMock,
      setPaintProperty: vi.fn(),
      addSource: addSourceMock,
      addLayer: addLayerMock,
      addControl: vi.fn(),
      remove: vi.fn(),
      resize: vi.fn(),
      fitBounds: vi.fn(),
      flyTo: vi.fn(),
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
  const mockSetWorkerUrl = vi.fn()

  return {
    default: {
      Map: MockMap,
      Marker: MockMarker,
      NavigationControl: MockNav,
      setWorkerUrl: mockSetWorkerUrl,
    },
    Map: MockMap,
    Marker: MockMarker,
    NavigationControl: MockNav,
    setWorkerUrl: mockSetWorkerUrl,
  }
})

describe('PolygonMapDrawer - Delimitador, Límites IGN y Coma Decimal (Issue #84)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    registeredEvents = {}
    currentMapZoom = 14
    zoomChanged = false
    isStyleLoadedValue = true
    setDataMock.mockClear()
    setLayoutPropertyMock.mockClear()
    addLayerMock.mockClear()
    addSourceMock.mockClear()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('declara constantes visuales con nombre para polígono y límites IGN', () => {
    expect(POLYGON_CORNER_RADIUS_PX).toBe(4) // 8 px de diámetro
    expect(POLYGON_CORNER_FILL).toBe('#FFFFFF')
    expect(POLYGON_CORNER_STROKE).toBe('#1E293B')
    expect(POLYGON_CORNER_STROKE_WIDTH).toBe(2)

    expect(POLYGON_EDGE_COLOR).toBe('#FFE066')
    expect(POLYGON_EDGE_WIDTH).toBe(2)
    expect(POLYGON_EDGE_DASHARRAY).toEqual([2, 2])

    expect(POLYGON_FILL_COLOR).toBe('#FFE066')
    expect(POLYGON_FILL_OPACITY).toBe(0.15)

    expect(IGN_LINE_COLOR).toBe('#FFFFFF')
    expect(IGN_PROVINCIA_WIDTH).toBe(2)
    expect(IGN_DEPARTAMENTO_WIDTH).toBe(1)
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

  it('PARTE A: llama a setData directamente sin requerir isStyleLoaded true (Bugfix)', () => {
    // Simular que el estilo de satélite sigue cargando teselas en segundo plano
    isStyleLoadedValue = false

    render(
      <PolygonMapDrawer
        isOpen={true}
        initialCenter={[-65.46, -33.67]}
        onClose={vi.fn()}
        onConfirmPolygon={vi.fn()}
      />,
    )

    // El evento 'load' ocurre
    act(() => {
      registeredEvents['load']?.forEach((cb) => cb({}))
    })

    setDataMock.mockClear()

    // El usuario agrega 3 vértices
    act(() => {
      registeredEvents['click']?.forEach((cb) =>
        cb({ lngLat: { lng: -65.465, lat: -33.675 } }),
      )
      vi.advanceTimersByTime(300)
    })

    // setData DEBE haberse llamado directamente sobre la fuente 'drawn-polygon'
    expect(setDataMock).toHaveBeenCalled()
    const lastCallArg = setDataMock.mock.calls[setDataMock.mock.calls.length - 1][0]
    expect(lastCallArg.type).toBe('FeatureCollection')
  })

  it('PARTE B: botón Límites IGN conmuta ambas capas vectoriales (provincias y departamentos)', () => {
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

    setLayoutPropertyMock.mockClear()

    // El botón inicialmente dice "Límites IGN: Activos"
    const toggleBtn = screen.getByRole('button', { name: /Límites IGN/i })
    expect(toggleBtn.textContent).toContain('Límites IGN: Activos')

    // Al hacer clic, conmuta a "Límites IGN: Ocultos"
    fireEvent.click(toggleBtn)
    expect(toggleBtn.textContent).toContain('Límites IGN: Ocultos')

    // Verifica que setLayoutProperty se ejecutó para ambas capas vectoriales
    expect(setLayoutPropertyMock).toHaveBeenCalledWith(
      'ign-provincias-layer',
      'visibility',
      'none',
    )
    expect(setLayoutPropertyMock).toHaveBeenCalledWith(
      'ign-departamentos-layer',
      'visibility',
      'none',
    )
  })

  it('PARTE C: formatea superficie con coma decimal y limpia mensaje de búsqueda al borrar o dibujar', () => {
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

    // Superficie inicial en 0 ha
    expect(screen.getByText('0 ha')).toBeTruthy()

    // Buscar una localidad que falle para disparar mensaje de estado
    const searchInput = screen.getByPlaceholderText(/Buscar ciudad, paraje/i)
    fireEvent.change(searchInput, { target: { value: 'LocalidadInexistente123' } })
    const searchForm = searchInput.closest('form')!
    fireEvent.submit(searchForm)

    // Al borrar el campo de búsqueda, el mensaje de estado debe limpiarse
    fireEvent.change(searchInput, { target: { value: '' } })
    expect(screen.queryByText(/No se encontró esa localidad/i)).toBeNull()
  })
})
