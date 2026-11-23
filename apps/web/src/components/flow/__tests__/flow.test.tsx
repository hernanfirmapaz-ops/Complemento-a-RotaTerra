import { useState } from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { StepNav, type FlowStep } from '../StepNav'
import { LotStep } from '../LotStep'
import { RainStep } from '../RainStep'
import { ResultStep } from '../ResultStep'
import type {
  FieldOut,
  RunoffRunOut,
  AgronomicToolkitOut,
  TerrainOut,
  AntecedentMoisture,
} from '../../../types/api'

// Mocks de datos representativos
const mockField1: FieldOut = {
  id: 'field-1',
  name: 'Lote Norte - San Luis',
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [-66.1, -33.2],
        [-66.08, -33.2],
        [-66.08, -33.18],
        [-66.1, -33.18],
        [-66.1, -33.2],
      ],
    ],
  },
  properties: {},
  area_ha: 145.5,
  declared_area_ha: 145.0,
  utm_epsg: 32719,
  centroid: [-66.09, -33.19],
  bbox: [-66.1, -33.2, -66.08, -33.18],
  warnings: [],
  created_at: '2026-11-20T10:00:00Z',
  source_file: null,
  has_terrain: true,
  has_hydrology: true,
}

const mockField2: FieldOut = {
  id: 'field-2',
  name: 'Lote Sur - Piedemonte',
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [-66.2, -33.4],
        [-66.18, -33.4],
        [-66.18, -33.38],
        [-66.2, -33.38],
        [-66.2, -33.4],
      ],
    ],
  },
  properties: {},
  area_ha: 89.2,
  declared_area_ha: 90.0,
  utm_epsg: 32719,
  centroid: [-66.19, -33.39],
  bbox: [-66.2, -33.4, -66.18, -33.38],
  warnings: [],
  created_at: '2026-11-20T11:00:00Z',
  source_file: null,
  has_terrain: true,
  has_hydrology: true,
}

const mockRun: RunoffRunOut = {
  id: 'run-123',
  field_id: 'field-1',
  name: 'Tormenta 80 mm - Normal',
  rainfall_event_id: 'rain-event-1',
  rainfall_event_name: 'Tormenta 80 mm',
  model: 'SCS-CN-2D',
  processing_version: '1.0.0',
  created_at: '2026-11-20T12:00:00Z',
  is_active: true,
  field_conditions: {},
  cn_result: {
    precipitation_mm: 80,
    cn_ii_base: 75,
    cn_effective: 75,
    antecedent_moisture: 'medium',
    lambda_ratio: 0.2,
    potential_retention_s_mm: 84.67,
    initial_abstraction_ia_mm: 16.93,
    infiltration_after_ia_f_mm: 35.2,
    total_retention_losses_mm: 52.13,
    runoff_q_mm: 27.87,
    runoff_coefficient: 0.348,
    mass_balance_error_mm: 0.0,
  },
  spatial_summary: {
    runoff_generated_q_mm: 27.87,
    field_runoff_generated_m3: 40550,
    external_runoff_inflow_m3: 12000,
    total_runoff_supply_m3: 52550,
    potential_depression_retention_m3: 8500,
    net_outflow_potential_m3: 44050,
    peak_discharge_m3_s: 4.2,
    max_cell_cumulative_runoff_m3: 1200,
    max_cell_runoff_load_mm: 85.0,
    mean_cell_runoff_load_mm: 36.2,
    high_concentration_area_ha: 14.8,
  },
  confidence: {
    level: 'alto',
    score: 0.88,
    reasons: ['Relieve Copernicus 30m validado', 'Suelo INTA GeoINTA confirmado'],
    relief_note: 'DEM satelital sin artefactos',
    soil_note: 'Serie San Ignacio franco arenoso',
    rain_note: 'Tormenta sintética 24h Huff',
  },
  hydrodynamic_2d_summary: {
    manning_n: 0.04,
    ponding_threshold_m: 0.05,
    hydraulic_structures_applied: 0,
    Effective_runoff_input_mm: 27.87,
    infiltration_losses_mm: 0.0,
    max_water_depth_in_field_m: 0.42,
    mean_max_water_depth_in_field_m: 0.08,
    final_retained_water_depth_max_m: 0.35,
    max_velocity_in_field_m_s: 1.15,
    max_unit_discharge_in_field_m2_s: 0.48,
    ponded_area_in_field_ha: 6.4,
    ponded_area_in_field_pct: 4.4,
    ponded_retained_volume_in_field_m3: 7200,
    domain_input_volume_m3: 52550,
    domain_final_storage_m3: 7200,
    domain_boundary_outflow_m3: 45350,
    mass_balance_relative_error: 0.001,
    solver_mode: 'diffusive',
  },
  assumptions_and_notes: [],
  warnings: [],
  limitations: [],
}

const mockToolkit: AgronomicToolkitOut = {
  field_id: 'field-1',
  processed_at: '2026-11-20T12:00:00Z',
  parameters: {},
  erosion_usle: {
    r_storm_mj_mm_ha_h: 450.0,
    k_factor: 0.035,
    c_factor: 0.18,
    p_factor: 0.8,
    ls_mean_in_field: 1.85,
    ls_max_in_field: 4.2,
    mean_soil_loss_t_ha: 4.1,
    max_soil_loss_t_ha: 18.2,
    total_field_soil_loss_tons: 596.55,
    gully_initiation_cells: 12,
    gully_risk_area_ha: 2.1,
    erosion_severity: 'moderada',
  },
  water_balance_monthly: {
    source: 'NASA POWER Climatology (1991-2020)',
    available_water_capacity_max_mm: 140.0,
    annual_precipitation_mm: 680.0,
    annual_et0_mm: 1120.0,
    deficit_months_count: 5,
    excess_months_count: 1,
    final_available_water_mm: 85.0,
    final_available_water_pct: 60.7,
    months: [],
  },
  warnings: [],
  limitations: [],
} as unknown as AgronomicToolkitOut

const mockTerrain: TerrainOut = {
  field_id: 'field-1',
  processing_version: '1.0.0',
  processed_at: '2026-11-20T10:05:00Z',
  parameters: {},
  source: {
    source_id: 'copernicus_glo30',
    source_name: 'Copernicus GLO-30 DEM',
    source_url: null,
    license: 'Open Access',
    surface_type: 'DSM',
    nominal_resolution_m: 30,
    vertical_datum: 'EGM96',
    vertical_accuracy_m: 2.5,
    vertical_accuracy_note: 'Global accuracy ~2m',
    acquisition_start: '2011-01-01',
    acquisition_end: '2015-12-31',
    acquisition_method: 'TanDEM-X radar',
  },
  quality: {
    pixel_size_m: 30,
    source_pixel_size_m: [30, 30],
    crs: 'EPSG:32719',
    vertical_datum: 'EGM96',
    vertical_accuracy_m: 2.5,
    surface_type: 'DSM',
    width: 100,
    height: 100,
    buffer_m: 200,
    cells_in_field: 1616,
    cells_in_area: 2500,
    nodata_pct_field: 0,
    nodata_pct_area: 0,
    elevation_field: { min: 610, max: 645, mean: 625, range: 35 },
    elevation_area: { min: 605, max: 650, mean: 624, range: 45 },
    field_area_ha: 145.5,
    warnings: [],
  },
  files: {},
  limitations: [],
}

describe('Flujo Lote -> Lluvia -> Resultado', () => {
  describe('Paso 1: StepNav (barra de progreso y navegación)', () => {
    it('muestra los tres pasos ordenados', () => {
      render(
        <StepNav
          currentStep="lote"
          completedSteps={[]}
          onSelectStep={vi.fn()}
        />,
      )

      expect(screen.getByText('1. Lote')).toBeInTheDocument()
      expect(screen.getByText('2. Lluvia')).toBeInTheDocument()
      expect(screen.getByText('3. Resultado')).toBeInTheDocument()
    })

    it('marca el paso activo con aria-current="step"', () => {
      render(
        <StepNav
          currentStep="lluvia"
          completedSteps={['lote']}
          onSelectStep={vi.fn()}
        />,
      )

      const activeBtn = screen.getByRole('button', { name: /2\. Lluvia/i })
      expect(activeBtn).toHaveAttribute('aria-current', 'step')
    })

    it('permite hacer clic en pasos completados pero no en pendientes', () => {
      const handleSelect = vi.fn()
      render(
        <StepNav
          currentStep="lluvia"
          completedSteps={['lote']}
          onSelectStep={handleSelect}
        />,
      )

      const loteBtn = screen.getByRole('button', { name: /1\. Lote/i })
      const resultadoBtn = screen.getByRole('button', { name: /3\. Resultado/i })

      expect(loteBtn).not.toBeDisabled()
      expect(resultadoBtn).toBeDisabled()

      fireEvent.click(loteBtn)
      expect(handleSelect).toHaveBeenCalledWith('lote')

      fireEvent.click(resultadoBtn)
      expect(handleSelect).not.toHaveBeenCalledWith('resultado')
    })

    it('muestra resúmenes de lote, lluvia y resultado si están provistos', () => {
      render(
        <StepNav
          currentStep="resultado"
          completedSteps={['lote', 'lluvia']}
          onSelectStep={vi.fn()}
          lotSummary="145 ha"
          rainSummary="80 mm"
          resultSummary="35% escurrimiento"
        />,
      )

      expect(screen.getByText('145 ha')).toBeInTheDocument()
      expect(screen.getByText('80 mm')).toBeInTheDocument()
      expect(screen.getByText('35% escurrimiento')).toBeInTheDocument()
    })
  })

  describe('Paso 1: LotStep (selección o carga de lote)', () => {
    it('renderiza la lista de lotes disponibles', () => {
      render(
        <LotStep
          fields={[mockField1, mockField2]}
          activeField={mockField1}
          onSelectField={vi.fn()}
          onOpenDrawer={vi.fn()}
          onFileUpload={vi.fn()}
          onContinue={vi.fn()}
          busy={false}
        />,
      )

      // Aparece en la lista de lotes analizados
      expect(screen.getAllByText('Lote Norte - San Luis').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('Lote Sur - Piedemonte')).toBeInTheDocument()
      expect(screen.getAllByText(/145\.5 ha/i).length).toBeGreaterThanOrEqual(1)
    })

    it('llama a onSelectField cuando el usuario elige otro lote', () => {
      const onSelect = vi.fn()
      render(
        <LotStep
          fields={[mockField1, mockField2]}
          activeField={mockField1}
          onSelectField={onSelect}
          onOpenDrawer={vi.fn()}
          onFileUpload={vi.fn()}
          onContinue={vi.fn()}
          busy={false}
        />,
      )

      const field2Btn = screen.getByRole('button', { name: /Lote Sur - Piedemonte/i })
      fireEvent.click(field2Btn)
      expect(onSelect).toHaveBeenCalledWith('field-2')
    })

    it('llama a onOpenDrawer al hacer clic en "Dibujar en el mapa satelital"', () => {
      const onOpenDrawer = vi.fn()
      render(
        <LotStep
          fields={[mockField1]}
          activeField={mockField1}
          onSelectField={vi.fn()}
          onOpenDrawer={onOpenDrawer}
          onFileUpload={vi.fn()}
          onContinue={vi.fn()}
          busy={false}
        />,
      )

      const drawBtn = screen.getByRole('button', { name: /Dibujar en el mapa satelital/i })
      fireEvent.click(drawBtn)
      expect(onOpenDrawer).toHaveBeenCalledTimes(1)
    })

    it('llama a onContinue cuando se presiona "Continuar a Lluvia →"', () => {
      const onContinue = vi.fn()
      render(
        <LotStep
          fields={[mockField1]}
          activeField={mockField1}
          onSelectField={vi.fn()}
          onOpenDrawer={vi.fn()}
          onFileUpload={vi.fn()}
          onContinue={onContinue}
          busy={false}
        />,
      )

      const continueBtn = screen.getByRole('button', { name: /Continuar a Lluvia/i })
      fireEvent.click(continueBtn)
      expect(onContinue).toHaveBeenCalledTimes(1)
    })

    it('deshabilita botones de acción cuando busy=true', () => {
      render(
        <LotStep
          fields={[mockField1]}
          activeField={mockField1}
          onSelectField={vi.fn()}
          onOpenDrawer={vi.fn()}
          onFileUpload={vi.fn()}
          onContinue={vi.fn()}
          busy={true}
        />,
      )

      expect(screen.getByRole('button', { name: /Dibujar en el mapa satelital/i })).toBeDisabled()
      expect(screen.getByRole('button', { name: /Continuar a Lluvia/i })).toBeDisabled()
    })
  })

  describe('Paso 2: RainStep (configuración de la lluvia)', () => {
    it('muestra los 3 escenarios predeterminados de lluvia (30, 80, 130 mm)', () => {
      render(
        <RainStep
          stormMm={80}
          onSelectMm={vi.fn()}
          amc="medium"
          onChangeAmc={vi.fn()}
          coverCode="soja_maiz_sd_buena"
          onChangeCoverCode={vi.fn()}
          dailyRainContext={null}
          selectedDate=""
          onChangeSelectedDate={vi.fn()}
          onSimulateDailyDate={vi.fn()}
          onSimulate={vi.fn()}
          onBack={vi.fn()}
          busy={false}
        />,
      )

      expect(screen.getByText(/Conservador 30 mm/i)).toBeInTheDocument()
      expect(screen.getByText(/Medio 80 mm/i)).toBeInTheDocument()
      expect(screen.getByText(/Crítico 130 mm/i)).toBeInTheDocument()
    })

    it('llama a onSelectMm al cambiar el escenario de milímetros', () => {
      const onSelectMm = vi.fn()
      render(
        <RainStep
          stormMm={80}
          onSelectMm={onSelectMm}
          amc="medium"
          onChangeAmc={vi.fn()}
          coverCode="soja_maiz_sd_buena"
          onChangeCoverCode={vi.fn()}
          dailyRainContext={null}
          selectedDate=""
          onChangeSelectedDate={vi.fn()}
          onSimulateDailyDate={vi.fn()}
          onSimulate={vi.fn()}
          onBack={vi.fn()}
          busy={false}
        />,
      )

      const opt130 = screen.getByRole('button', { name: /Crítico 130 mm/i })
      fireEvent.click(opt130)
      expect(onSelectMm).toHaveBeenCalledWith(130)
    })

    it('llama a onSimulate al presionar "Simular lluvia de ..."', () => {
      const onSimulate = vi.fn()
      render(
        <RainStep
          stormMm={80}
          onSelectMm={vi.fn()}
          amc="medium"
          onChangeAmc={vi.fn()}
          coverCode="soja_maiz_sd_buena"
          onChangeCoverCode={vi.fn()}
          dailyRainContext={null}
          selectedDate=""
          onChangeSelectedDate={vi.fn()}
          onSimulateDailyDate={vi.fn()}
          onSimulate={onSimulate}
          onBack={vi.fn()}
          busy={false}
        />,
      )

      const simBtn = screen.getByRole('button', { name: /Simular lluvia de 80 mm/i })
      fireEvent.click(simBtn)
      expect(onSimulate).toHaveBeenCalledTimes(1)
    })

    it('llama a onBack al presionar "Cambiar de lote"', () => {
      const onBack = vi.fn()
      render(
        <RainStep
          stormMm={80}
          onSelectMm={vi.fn()}
          amc="medium"
          onChangeAmc={vi.fn()}
          coverCode="soja_maiz_sd_buena"
          onChangeCoverCode={vi.fn()}
          dailyRainContext={null}
          selectedDate=""
          onChangeSelectedDate={vi.fn()}
          onSimulateDailyDate={vi.fn()}
          onSimulate={vi.fn()}
          onBack={onBack}
          busy={false}
        />,
      )

      const backBtn = screen.getByRole('button', { name: /Cambiar de lote/i })
      fireEvent.click(backBtn)
      expect(onBack).toHaveBeenCalledTimes(1)
    })
  })

  describe('Paso 3: ResultStep (presentación de resultados y métricas)', () => {
    it('muestra las métricas clave de escurrimiento, anegamiento y erosión', () => {
      render(
        <ResultStep
          stormMm={80}
          run={mockRun}
          runsList={[mockRun]}
          toolkit={mockToolkit}
          terrain={mockTerrain}
          activeOverlay="waterlogging"
          onSelectOverlay={vi.fn()}
          onReplayRain={vi.fn()}
          onChangeLot={vi.fn()}
          busy={false}
        />,
      )

      // Escurrimiento 35%
      expect(screen.getByText('35')).toBeInTheDocument()
      expect(screen.getByText('Escurre fuera del lote')).toBeInTheDocument()

      // Anegamiento 6.4 ha
      expect(screen.getByText('6.4')).toBeInTheDocument()
      expect(screen.getByText('Superficie anegable')).toBeInTheDocument()

      // Erosión USLE 4.1 t/ha
      expect(screen.getByText('4.1')).toBeInTheDocument()
      expect(screen.getByText('Pérdida de suelo')).toBeInTheDocument()
    })

    it('muestra nivel de confianza del resultado', () => {
      render(
        <ResultStep
          stormMm={80}
          run={mockRun}
          runsList={[mockRun]}
          toolkit={mockToolkit}
          terrain={mockTerrain}
          activeOverlay="waterlogging"
          onSelectOverlay={vi.fn()}
          onReplayRain={vi.fn()}
          onChangeLot={vi.fn()}
          busy={false}
        />,
      )

      expect(screen.getByText(/Indicador de confianza: Alto/i)).toBeInTheDocument()
    })

    it('permite cambiar la capa activa del visor 3D', () => {
      const onSelectOverlay = vi.fn()
      render(
        <ResultStep
          stormMm={80}
          run={mockRun}
          runsList={[mockRun]}
          toolkit={mockToolkit}
          terrain={mockTerrain}
          activeOverlay="waterlogging"
          onSelectOverlay={onSelectOverlay}
          onReplayRain={vi.fn()}
          onChangeLot={vi.fn()}
          busy={false}
        />,
      )

      // Clic en la capa de erosión
      const erosionLayer = screen.getByText('Pérdida de suelo y cárcavas')
      fireEvent.click(erosionLayer)
      expect(onSelectOverlay).toHaveBeenCalledWith('erosion')
    })

    it('llama a onChangeLot y onReplayRain en los botones de acción', () => {
      const onChangeLot = vi.fn()
      const onReplayRain = vi.fn()
      render(
        <ResultStep
          stormMm={80}
          run={mockRun}
          runsList={[mockRun]}
          toolkit={mockToolkit}
          terrain={mockTerrain}
          activeOverlay="waterlogging"
          onSelectOverlay={vi.fn()}
          onReplayRain={onReplayRain}
          onChangeLot={onChangeLot}
          busy={false}
        />,
      )

      fireEvent.click(screen.getByRole('button', { name: /Cambiar de lote/i }))
      expect(onChangeLot).toHaveBeenCalledTimes(1)

      fireEvent.click(screen.getByRole('button', { name: /Probar otra lluvia/i }))
      expect(onReplayRain).toHaveBeenCalledTimes(1)
    })

    it('maneja datos nulos sin fallar (modo sin simulación)', () => {
      render(
        <ResultStep
          stormMm={80}
          run={null}
          runsList={[]}
          toolkit={null}
          terrain={null}
          activeOverlay="waterlogging"
          onSelectOverlay={vi.fn()}
          onReplayRain={vi.fn()}
          onChangeLot={vi.fn()}
          busy={false}
        />,
      )

      // Valores nulos renderizan guiones o fallback
      expect(screen.getByText('Superficie anegable')).toBeInTheDocument()
      expect(screen.getByText('Escurre fuera del lote')).toBeInTheDocument()
      expect(screen.getByText('Pérdida de suelo')).toBeInTheDocument()
      expect(screen.getAllByText('Sin dato').length).toBeGreaterThanOrEqual(1)
    })
  })

  describe('Integración: Flujo completo interactivo (Lote -> Lluvia -> Resultado)', () => {
    function SimulatedAppFlow() {
      const [step, setStep] = useState<FlowStep>('lote')
      const [completed, setCompleted] = useState<FlowStep[]>([])
      const [activeField, setActiveField] = useState<FieldOut | null>(mockField1)
      const [stormMm, setStormMm] = useState<number>(80)
      const [amc, setAmc] = useState<AntecedentMoisture>('medium')
      const [coverCode, setCoverCode] = useState<string>('soja_maiz_sd_buena')
      const [run, setRun] = useState<RunoffRunOut | null>(null)

      const handleContinueLot = () => {
        if (!completed.includes('lote')) {
          setCompleted([...completed, 'lote'])
        }
        setStep('lluvia')
      }

      const handleSimulate = () => {
        if (!completed.includes('lluvia')) {
          setCompleted([...completed, 'lluvia'])
        }
        setRun(mockRun)
        setStep('resultado')
      }

      const handleBackToLot = () => setStep('lote')
      const handleReplayRain = () => setStep('lluvia')

      return (
        <div data-testid="app-flow-container">
          <StepNav
            currentStep={step}
            completedSteps={completed}
            onSelectStep={setStep}
            lotSummary={activeField ? `${Math.round(activeField.area_ha)} ha` : null}
            rainSummary={`${stormMm} mm`}
            resultSummary={run ? `${Math.round(run.cn_result.runoff_coefficient * 100)}% escurrimiento` : null}
          />

          {step === 'lote' && (
            <LotStep
              fields={[mockField1, mockField2]}
              activeField={activeField}
              onSelectField={(id) => {
                const found = [mockField1, mockField2].find((f) => f.id === id) ?? null
                setActiveField(found)
              }}
              onOpenDrawer={vi.fn()}
              onFileUpload={vi.fn()}
              onContinue={handleContinueLot}
              busy={false}
            />
          )}

          {step === 'lluvia' && (
            <RainStep
              stormMm={stormMm}
              onSelectMm={setStormMm}
              amc={amc}
              onChangeAmc={setAmc}
              coverCode={coverCode}
              onChangeCoverCode={setCoverCode}
              dailyRainContext={null}
              selectedDate=""
              onChangeSelectedDate={vi.fn()}
              onSimulateDailyDate={vi.fn()}
              onSimulate={handleSimulate}
              onBack={handleBackToLot}
              busy={false}
            />
          )}

          {step === 'resultado' && (
            <ResultStep
              stormMm={stormMm}
              run={run}
              runsList={run ? [run] : []}
              toolkit={mockToolkit}
              terrain={mockTerrain}
              activeOverlay="waterlogging"
              onSelectOverlay={vi.fn()}
              onReplayRain={handleReplayRain}
              onChangeLot={handleBackToLot}
              busy={false}
            />
          )}
        </div>
      )
    }

    it('navega de punta a punta: lote seleccionado -> lluvia elegida -> simulación -> resultado visible', () => {
      render(<SimulatedAppFlow />)

      // 1. Iniciamos en paso "lote": vemos título y botón de continuar
      expect(screen.getByText('Elegí tu lote')).toBeInTheDocument()
      expect(screen.getAllByText('Lote Norte - San Luis').length).toBeGreaterThanOrEqual(1)

      const btnContinuarLluvia = screen.getByRole('button', { name: /Continuar a Lluvia/i })
      fireEvent.click(btnContinuarLluvia)

      // 2. Pasamos a paso "lluvia": vemos opciones de precipitación
      expect(screen.getByText('¿Cuánto llueve?')).toBeInTheDocument()
      expect(screen.getByText(/Medio 80 mm/i)).toBeInTheDocument()

      // Cambiamos a lluvia de 130 mm
      const opt130 = screen.getByRole('button', { name: /Crítico 130 mm/i })
      fireEvent.click(opt130)

      // Hacemos clic en simular
      const btnSimular = screen.getByRole('button', { name: /Simular lluvia de 130 mm/i })
      fireEvent.click(btnSimular)

      // 3. Pasamos a paso "resultado": vemos las métricas y capas
      expect(screen.getByText(/Qué pasó con 130 mm/i)).toBeInTheDocument()
      expect(screen.getByText('35')).toBeInTheDocument()
      expect(screen.getByText('6.4')).toBeInTheDocument()

      // 4. Volver a lluvia con "Probar otra lluvia"
      const btnProbarOtra = screen.getByRole('button', { name: /Probar otra lluvia/i })
      fireEvent.click(btnProbarOtra)
      expect(screen.getByText('¿Cuánto llueve?')).toBeInTheDocument()

      // 5. Volver a lote con StepNav
      const navLoteBtn = screen.getByRole('button', { name: /1\. Lote/i })
      fireEvent.click(navLoteBtn)
      expect(screen.getByText('Elegí tu lote')).toBeInTheDocument()
    })
  })
})
