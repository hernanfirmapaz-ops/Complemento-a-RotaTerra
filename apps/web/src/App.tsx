import { lazy, Suspense, useEffect, useState } from 'react'
import {
  activateRunoffRun,
  compareScenarios,
  createManualRainfallEvent,
  executeRunoffRun,
  exportGeoJsonUrl,
  exportReportUrl,
  getAgronomicToolkit,
  getDailyRainfallContext,
  getRunoffTimeline,
  getStaticHydrology,
  getTerrain,
  getTerrainMesh,
  importFieldGeoJSON,
  listFieldObservations,
  listFields,
  listRainfallEvents,
  listRunoffRuns,
  processTerrain,
  queryTerrainPoint,
  runAgronomicToolkit,
  runHydrodynamic2DSolver,
  runStaticHydrology,
  simulateDailyRainfall,
} from './services/api'
import type {
  AgronomicToolkitIn,
  AgronomicToolkitOut,
  AntecedentMoisture,
  DailyRainfallContextOut,
  FieldObservationOut,
  FieldOut,
  HydrologyOut,
  MeshOut,
  PointOut,
  RainfallEventOut,
  RunoffRunOut,
  RunoffTimelineOut,
  SoilGroup,
  TerrainOut,
} from './types/api'
import type { AgronomistOverlayMode } from './components/TerrainDiorama3D'
import { Segmented } from './components/ui/Segmented'
import { Button } from './components/ui/Button'
import { BottomSheet, type BottomSheetSnap } from './components/ui/BottomSheet'
import { Icon } from './components/ui/Icon'
import { StepNav, type FlowStep } from './components/flow/StepNav'
import { LotStep } from './components/flow/LotStep'
import { RainStep } from './components/flow/RainStep'
import { ResultStep } from './components/flow/ResultStep'

const TerrainDiorama3D = lazy(() =>
  import('./components/TerrainDiorama3D').then((m) => ({ default: m.TerrainDiorama3D })),
)
const TerrainScene3D = lazy(() =>
  import('./components/TerrainScene3D').then((m) => ({ default: m.TerrainScene3D })),
)
const PolygonMapDrawer = lazy(() =>
  import('./components/PolygonMapDrawer').then((m) => ({ default: m.PolygonMapDrawer })),
)
const AgronomicToolkitPanel = lazy(() =>
  import('./components/AgronomicToolkitPanel').then((m) => ({ default: m.AgronomicToolkitPanel })),
)
const ComponentShowcase = lazy(() =>
  import('./components/ui/ComponentShowcase').then((m) => ({ default: m.ComponentShowcase })),
)

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth < 768 : false,
  )

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return isMobile
}

export function App() {
  const isMobile = useIsMobile()
  const [sheetSnap, setSheetSnap] = useState<BottomSheetSnap>('half')

  // Estado del flujo de 3 pasos (SDD-002)
  const [flowStep, setFlowStep] = useState<FlowStep>('lote')
  const [workspaceView, setWorkspaceView] = useState<'3d' | 'map'>('3d')

  // Datos principales del lote y simulación
  const [fields, setFields] = useState<FieldOut[]>([])
  const [activeFieldId, setActiveFieldId] = useState<string | null>(null)
  const [terrain, setTerrain] = useState<TerrainOut | null>(null)
  const [mesh, setMesh] = useState<MeshOut | null>(null)
  const [hydrology, setHydrology] = useState<HydrologyOut | null>(null)
  const [, setRainfallEvents] = useState<RainfallEventOut[]>([])
  const [runoffRuns, setRunoffRuns] = useState<RunoffRunOut[]>([])
  const [, setTimeline] = useState<RunoffTimelineOut | null>(null)
  const [, setTimelineStep] = useState<number>(0)
  const [, setObservations] = useState<FieldObservationOut[]>([])
  const [toolkit, setToolkit] = useState<AgronomicToolkitOut | null>(null)

  // Modales y herramientas
  const [isMapDrawerOpen, setIsMapDrawerOpen] = useState<boolean>(false)
  const [isToolkitModalOpen, setIsToolkitModalOpen] = useState<boolean>(false)
  const [showComponentShowcase, setShowComponentShowcase] = useState<boolean>(
    () =>
      typeof window !== 'undefined' &&
      (window.location.hash === '#showcase' || window.location.hash === '#ui'),
  )

  // Configuración de visualización y lluvia
  const [dioramaOverlay, setDioramaOverlay] =
    useState<AgronomistOverlayMode>('waterlogging')
  const [isPlayingDioramaRain, setIsPlayingDioramaRain] = useState<boolean>(false)
  const [quickRainMm, setQuickRainMm] = useState<number>(80)
  const [quickSoilGroup, setQuickSoilGroup] = useState<SoilGroup>('B')
  const [quickAmc, setQuickAmc] = useState<AntecedentMoisture>('medium')
  const [quickCover, setQuickCover] = useState<string>('soja_maiz_sd_buena')
  const [dailyRainContext, setDailyRainContext] =
    useState<DailyRainfallContextOut | null>(null)
  const [selectedDailyDate, setSelectedDailyDate] = useState<string>('')
  const [exaggeration, setExaggeration] = useState<number>(2.5)
  const [selectedPoint, setSelectedPoint] = useState<PointOut | null>(null)

  // Estados de carga y error
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const activeField = fields.find((f) => f.id === activeFieldId) ?? null
  const activeRun =
    runoffRuns.find((r) => r.is_active) ?? runoffRuns[0] ?? null

  // Carga inicial de lotes disponibles
  useEffect(() => {
    listFields()
      .then((list) => {
        setFields(list)
        if (list.length > 0) setActiveFieldId(list[0].id)
      })
      .catch((err: Error) => setError(err.message))
  }, [])

  // Cargar datos cuando cambia el lote activo
  useEffect(() => {
    setTerrain(null)
    setMesh(null)
    setHydrology(null)
    setRainfallEvents([])
    setRunoffRuns([])
    setTimeline(null)
    setObservations([])
    setToolkit(null)
    setDailyRainContext(null)
    setSelectedDailyDate('')
    setSelectedPoint(null)
    if (!activeField) return
    if (!activeField.has_terrain) return

    setBusy('Cargando relieve 3D del lote y simulaciones...')
    const tasks: Promise<unknown>[] = [
      getTerrain(activeField.id),
      getTerrainMesh(activeField.id),
      activeField.has_hydrology
        ? getStaticHydrology(activeField.id).catch(() => null)
        : Promise.resolve(null),
      listRainfallEvents(activeField.id).catch(() => []),
      listRunoffRuns(activeField.id).catch(() => []),
      listFieldObservations(activeField.id).catch(() => []),
      getAgronomicToolkit(activeField.id).catch(() => null),
      getDailyRainfallContext(activeField.id).catch(() => null),
    ]
    Promise.all(tasks)
      .then(async ([t, m, h, evs, rns, obs, tk, dctx]) => {
        setTerrain(t as TerrainOut)
        setMesh(m as MeshOut)
        setHydrology((h as HydrologyOut | null) ?? null)
        setRainfallEvents(evs as RainfallEventOut[])
        const runsList = rns as RunoffRunOut[]
        setRunoffRuns(runsList)
        setObservations(obs as FieldObservationOut[])
        setToolkit((tk as AgronomicToolkitOut | null) ?? null)
        const daily = (dctx as DailyRainfallContextOut | null) ?? null
        setDailyRainContext(daily)
        if (daily?.selected_day) {
          setSelectedDailyDate(daily.selected_day.date)
        }
        const act = runsList.find((r) => r.is_active) ?? runsList[0] ?? null
        if (act) {
          setQuickRainMm(Math.round(act.cn_result.precipitation_mm))
          const tl = await getRunoffTimeline(activeField.id, act.id).catch(
            () => null,
          )
          setTimeline(tl)
          setTimelineStep(tl?.peak_step_index ?? 0)
        } else if (daily?.selected_day) {
          setQuickRainMm(Math.round(daily.selected_day.precipitation_mm))
          setQuickAmc(daily.selected_day.antecedent_moisture_amc)
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(null))
  }, [activeField?.id, activeField?.has_terrain, activeField?.has_hydrology])

  /** Simulación de tormenta de diseño sobre el terreno 3D */
  const handleQuickSimulateRain = async (
    mmOverride?: number,
    amcOverride?: AntecedentMoisture,
    coverOverride?: string,
    soilOverride?: SoilGroup,
  ) => {
    if (!activeField) return
    const mm = mmOverride ?? quickRainMm
    const amc = amcOverride ?? quickAmc
    const cov = coverOverride ?? quickCover
    const soil = soilOverride ?? quickSoilGroup
    setQuickRainMm(mm)
    setQuickAmc(amc)
    setQuickCover(cov)
    setQuickSoilGroup(soil)

    setError(null)
    setBusy(`Simulando tormenta de ${mm} mm sobre el terreno 3D...`)
    try {
      if (!terrain) {
        await processTerrain(activeField.id, {
          sourceId: 'copernicus_glo30',
          bufferM: 300,
        })
      }
      let presetLabel = `Lluvia ${mm} mm`
      if (mm === 30) presetLabel = 'Conservador (30 mm) · Lluvia suave'
      else if (mm === 80) presetLabel = 'Medio (80 mm) · Tormenta de diseño'
      else if (mm === 130) presetLabel = 'Crítico (130 mm) · Crecida extraordinaria'

      const ev = await createManualRainfallEvent(activeField.id, {
        name: presetLabel,
        total_mm: mm,
        source_type: 'manual',
      })
      const created = await executeRunoffRun(activeField.id, {
        name: `${presetLabel} · Suelo ${soil} · ${
          amc === 'wet' ? 'Húmedo' : amc === 'dry' ? 'Seco' : 'Normal'
        }`,
        rainfall_event_id: ev.id,
        soil_group: soil,
        cover_code: cov,
        antecedent_moisture: amc,
        compaction_high: false,
        lambda_ratio: 0.2,
      })
      await runHydrodynamic2DSolver(activeField.id, created.id, {
        ponding_threshold_m: 0.05,
        recession_minutes: 30,
      })
      const tk = await runAgronomicToolkit(activeField.id, {
        soil_group: soil,
        cover_code: cov,
        storm_precipitation_mm: mm,
        crop_code:
          (toolkit?.parameters?.crop_code as string) || 'maiz_temprano',
        environment_zone: 'media_loma',
      })
      const [t, m, h, evs, rns, all] = await Promise.all([
        getTerrain(activeField.id),
        getTerrainMesh(activeField.id),
        getStaticHydrology(activeField.id),
        listRainfallEvents(activeField.id),
        listRunoffRuns(activeField.id),
        listFields(),
      ])
      setTerrain(t)
      setMesh(m)
      setHydrology(h)
      setRainfallEvents(evs)
      setRunoffRuns(rns)
      setToolkit(tk)
      setFields(all)
      setIsPlayingDioramaRain(true)
      setFlowStep('resultado')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  /** Simulación de lluvia diaria histórica satelital NASA POWER */
  const handleSimulateDailyRain = async (dateStr?: string) => {
    if (!activeField) return
    const target =
      dateStr || selectedDailyDate || dailyRainContext?.selected_day?.date
    if (!target) return
    setError(null)
    setBusy(`Consultando lluvia NASA POWER para el día ${target}...`)
    try {
      if (!terrain) {
        await processTerrain(activeField.id, {
          sourceId: 'copernicus_glo30',
          bufferM: 300,
        })
      }
      const res = await simulateDailyRainfall(activeField.id, {
        date: target,
        soil_group: quickSoilGroup,
        cover_code: quickCover,
      })
      setDailyRainContext(res.context)
      setSelectedDailyDate(target)
      setQuickRainMm(Math.round(res.event.total_mm))
      setQuickAmc(res.context.selected_day?.antecedent_moisture_amc ?? 'medium')

      await runHydrodynamic2DSolver(activeField.id, res.runoff_run.id, {
        ponding_threshold_m: 0.05,
        recession_minutes: 30,
      })
      const tk = await runAgronomicToolkit(activeField.id, {
        soil_group: quickSoilGroup,
        cover_code: quickCover,
        storm_precipitation_mm: Math.max(1.0, res.event.total_mm),
        crop_code: 'maiz_temprano',
        environment_zone: 'media_loma',
      })
      setToolkit(tk)

      const evs = await listRainfallEvents(activeField.id).catch(() => [])
      setRainfallEvents(evs)
      const rns = await listRunoffRuns(activeField.id).catch(() => [])
      setRunoffRuns(rns)
      const tl = await getRunoffTimeline(activeField.id, res.runoff_run.id).catch(
        () => null,
      )
      setTimeline(tl)
      setTimelineStep(tl?.peak_step_index ?? 0)
      setIsPlayingDioramaRain(true)
      setFlowStep('resultado')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  /** Importación completa de un archivo de lote con cálculo inmediato de relieve e hidrología */
  const handleFullImportAndSimulate = async (
    file: File,
    customName?: string,
  ) => {
    setError(null)
    setBusy(
      `Paso 1/4: Guardando polígono de "${customName || file.name}" y validando hectáreas...`,
    )
    try {
      const imported = await importFieldGeoJSON(file, customName)
      const fld = imported[0]
      if (fld) {
        setBusy(
          `Paso 2/4: Descargando relieve satelital Copernicus (30 m) para ${fld.name}...`,
        )
        await processTerrain(fld.id, {
          sourceId: 'copernicus_glo30',
          bufferM: 300,
        })
        setBusy(
          'Paso 3/4: Calculando pendientes, vaguadas y red de drenaje MFD...',
        )
        await runStaticHydrology(fld.id, {
          conditioning_mode: 'fill_small',
          max_fill_depth_m: 0.35,
          max_fill_area_m2: 4500,
          mfd_exponent: 1.1,
          routing_basis: 'MFD',
        })
        const ev = await createManualRainfallEvent(fld.id, {
          name: `Lluvia ${quickRainMm} mm`,
          total_mm: quickRainMm,
          source_type: 'manual',
        })
        const created = await executeRunoffRun(fld.id, {
          name: `${quickRainMm} mm · Suelo ${quickSoilGroup} · Siembra Directa`,
          rainfall_event_id: ev.id,
          soil_group: quickSoilGroup,
          cover_code: quickCover,
          antecedent_moisture: quickAmc,
          compaction_high: false,
          lambda_ratio: 0.2,
        })
        await runHydrodynamic2DSolver(fld.id, created.id, {
          ponding_threshold_m: 0.05,
          recession_minutes: 30,
        })
        setBusy('Paso 4/4: Generando diagnóstico agronómico INTA / NASA...')
        await runAgronomicToolkit(fld.id, {
          soil_group: quickSoilGroup,
          cover_code: quickCover,
          storm_precipitation_mm: quickRainMm,
          crop_code: 'maiz_temprano',
          environment_zone: 'media_loma',
        })
      }
      const all = await listFields()
      setFields(all)
      if (fld) {
        setActiveFieldId(fld.id)
        setFlowStep('resultado')
      }
      setIsMapDrawerOpen(false)
    } catch (err) {
      setError((err as Error).message)
      throw err
    } finally {
      setBusy(null)
    }
  }

  const handleImportGeoJSON = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    await handleFullImportAndSimulate(file, file.name.replace(/\.[^.]+$/, ''))
  }

  const handleRunToolkit = async (params: AgronomicToolkitIn) => {
    if (!activeField) return
    setError(null)
    setBusy('Calculando herramientas agronómicas...')
    try {
      const res = await runAgronomicToolkit(activeField.id, params)
      setToolkit(res)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleActivateRun = async (runId: string) => {
    if (!activeField) return
    setError(null)
    setBusy('Cambiando al escenario seleccionado...')
    try {
      await activateRunoffRun(activeField.id, runId)
      const [rns, m] = await Promise.all([
        listRunoffRuns(activeField.id),
        getTerrainMesh(activeField.id),
      ])
      setRunoffRuns(rns)
      setMesh(m)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleMapClick = async (lon: number, lat: number) => {
    if (!activeField) return
    try {
      const pt = await queryTerrainPoint(activeField.id, lon, lat)
      setSelectedPoint(pt)
    } catch {
      // Ignorar clicks fuera del lote
    }
  }

  // Resúmenes de los pasos para el StepNav
  const lotSummary = activeField ? `${activeField.name} (${activeField.area_ha.toFixed(0)} ha)` : null
  const rainSummary = activeRun ? `${quickRainMm} mm` : null
  const resultSummary = activeRun ? `${Math.round(activeRun.cn_result.runoff_coefficient * 100)}% escurre` : null

  // Pasos completados
  const completedSteps: FlowStep[] = []
  if (activeField) completedSteps.push('lote')
  if (activeRun) completedSteps.push('lluvia')
  if (activeRun && flowStep === 'resultado') completedSteps.push('resultado')

  if (showComponentShowcase) {
    return (
      <Suspense fallback={<div className="diorama-loading" style={{ padding: 32 }}>Cargando catálogo...</div>}>
        <ComponentShowcase
          onClose={() => {
            setShowComponentShowcase(false)
            if (window.location.hash) window.location.hash = ''
          }}
        />
      </Suspense>
    )
  }

  return (
    <div className="app-shell-3step">
      {/* TopBar minimalista de 56 px con presupuesto de botones controlado (≤ 6 en pantalla inicial) */}
      <header className="flow-topbar">
        <div className="flow-brand-group">
          <h1 className="flow-brand-title">RotaTerra</h1>
        </div>

        <div className="flow-topbar-actions">
          <Segmented
            value={workspaceView}
            onChange={(val) => setWorkspaceView(val as '3d' | 'map')}
            options={[
              { value: '3d', label: '3D' },
              { value: 'map', label: 'Mapa' },
            ]}
          />

          {!isMobile && import.meta.env.DEV && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowComponentShowcase(true)}
              title="Ver catálogo de componentes del sistema de diseño (SDD-002)"
            >
              Galería UI
            </Button>
          )}

          {!isMobile && activeField && terrain && (
            <>
              <Button
                variant="text"
                size="sm"
                onClick={() => window.open(exportGeoJsonUrl(activeField.id), '_blank')}
              >
                Capas GIS ↓
              </Button>
              <Button
                variant="text"
                size="sm"
                onClick={() => window.open(exportReportUrl(activeField.id), '_blank')}
              >
                Informe PDF →
              </Button>
            </>
          )}
        </div>
      </header>

      {/* Mensajes de error en toast accesible */}
      {error && (
        <div className="error-toast" role="alert" style={{ margin: '8px 16px' }}>
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            aria-label="Cerrar"
            style={{ display: 'inline-flex', alignItems: 'center' }}
          >
            <Icon name="x" size={14} />
          </button>
        </div>
      )}

      {/* Layout principal: Panel izquierdo 380 px + Visor central (≥ 65%) */}
      <div className="flow-main">
        {!isMobile ? (
          <aside className="flow-sidebar">
            <StepNav
              currentStep={flowStep}
              completedSteps={completedSteps}
              onSelectStep={(step) => setFlowStep(step)}
              lotSummary={lotSummary}
              rainSummary={rainSummary}
              resultSummary={resultSummary}
            />

            {flowStep === 'lote' && (
              <LotStep
                fields={fields}
                activeField={activeField}
                onSelectField={(id) => {
                  setActiveFieldId(id)
                  setFlowStep('lluvia')
                }}
                onOpenDrawer={() => setIsMapDrawerOpen(true)}
                onFileUpload={handleImportGeoJSON}
                onContinue={() => setFlowStep('lluvia')}
                busy={Boolean(busy)}
              />
            )}

            {flowStep === 'lluvia' && (
              <RainStep
                stormMm={quickRainMm}
                onSelectMm={(mm) => setQuickRainMm(mm)}
                amc={quickAmc}
                onChangeAmc={setQuickAmc}
                coverCode={quickCover}
                onChangeCoverCode={setQuickCover}
                dailyRainContext={dailyRainContext}
                selectedDate={selectedDailyDate}
                onChangeSelectedDate={setSelectedDailyDate}
                onSimulateDailyDate={(date) => handleSimulateDailyRain(date)}
                onSimulate={() => handleQuickSimulateRain()}
                onBack={() => setFlowStep('lote')}
                busy={Boolean(busy)}
              />
            )}

            {flowStep === 'resultado' && (
              <ResultStep
                stormMm={quickRainMm}
                run={activeRun}
                runsList={runoffRuns}
                toolkit={toolkit}
                terrain={terrain}
                activeOverlay={dioramaOverlay}
                onSelectOverlay={setDioramaOverlay}
                onReplayRain={() => setFlowStep('lluvia')}
                onChangeLot={() => setFlowStep('lote')}
                onOpenToolkit={() => setIsToolkitModalOpen(true)}
                onCompareRuns={(a, b) =>
                  activeField
                    ? compareScenarios(activeField.id, a, b)
                    : Promise.resolve(null)
                }
                onActivateRun={handleActivateRun}
                busy={Boolean(busy)}
              />
            )}
          </aside>
        ) : (
          <BottomSheet
            snap={sheetSnap}
            onSnapChange={setSheetSnap}
            headerTitle={
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600 }}>
                <span>
                  {flowStep === 'lote' && '1. Elegí tu lote'}
                  {flowStep === 'lluvia' && `2. Lluvia (${quickRainMm} mm)`}
                  {flowStep === 'resultado' && '3. Resultados del lote'}
                </span>
              </div>
            }
            headerAction={
              <Button
                variant="text"
                size="sm"
                onClick={() => setSheetSnap(sheetSnap === 'collapsed' ? 'half' : 'collapsed')}
              >
                {sheetSnap === 'collapsed' ? 'Abrir ↑' : 'Plegar ↓'}
              </Button>
            }
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <StepNav
                currentStep={flowStep}
                completedSteps={completedSteps}
                onSelectStep={(step) => {
                  setFlowStep(step)
                  setSheetSnap('half')
                }}
                lotSummary={lotSummary}
                rainSummary={rainSummary}
                resultSummary={resultSummary}
              />

              {flowStep === 'lote' && (
                <LotStep
                  fields={fields}
                  activeField={activeField}
                  onSelectField={(id) => {
                    setActiveFieldId(id)
                    setFlowStep('lluvia')
                    setSheetSnap('half')
                  }}
                  onOpenDrawer={() => setIsMapDrawerOpen(true)}
                  onFileUpload={handleImportGeoJSON}
                  onContinue={() => setFlowStep('lluvia')}
                  busy={Boolean(busy)}
                />
              )}

              {flowStep === 'lluvia' && (
                <RainStep
                  stormMm={quickRainMm}
                  onSelectMm={(mm) => setQuickRainMm(mm)}
                  amc={quickAmc}
                  onChangeAmc={setQuickAmc}
                  coverCode={quickCover}
                  onChangeCoverCode={setQuickCover}
                  dailyRainContext={dailyRainContext}
                  selectedDate={selectedDailyDate}
                  onChangeSelectedDate={setSelectedDailyDate}
                  onSimulateDailyDate={(date) => {
                    handleSimulateDailyRain(date)
                    setSheetSnap('half')
                  }}
                  onSimulate={() => {
                    handleQuickSimulateRain()
                    setSheetSnap('half')
                  }}
                  onBack={() => setFlowStep('lote')}
                  busy={Boolean(busy)}
                />
              )}

              {flowStep === 'resultado' && (
                <ResultStep
                  stormMm={quickRainMm}
                  run={activeRun}
                  runsList={runoffRuns}
                  toolkit={toolkit}
                  terrain={terrain}
                  activeOverlay={dioramaOverlay}
                  onSelectOverlay={setDioramaOverlay}
                  onReplayRain={() => setFlowStep('lluvia')}
                  onChangeLot={() => setFlowStep('lote')}
                  onOpenToolkit={() => setIsToolkitModalOpen(true)}
                  onCompareRuns={(a, b) =>
                    activeField
                      ? compareScenarios(activeField.id, a, b)
                      : Promise.resolve(null)
                  }
                  onActivateRun={handleActivateRun}
                  busy={Boolean(busy)}
                />
              )}
            </div>
          </BottomSheet>
        )}

        {/* Visor 3D o Mapa 2D */}
        <main className="flow-stage">
          {workspaceView === '3d' ? (
            <div style={{ width: '100%', height: '100%', position: 'relative' }}>
              <Suspense
                fallback={
                  <div
                    style={{
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--ink-2)',
                      fontSize: 13,
                    }}
                  >
                    Cargando visor 3D...
                  </div>
                }
              >
                <TerrainDiorama3D
                  field={activeField}
                  mesh={mesh}
                  overlayMode={dioramaOverlay}
                  exaggeration={exaggeration}
                  onChangeExaggeration={setExaggeration}
                  rainIntensityFactor={Math.min(1.8, Math.max(0.2, quickRainMm / 70.0))}
                  showBoundary={true}
                  showContours={false}
                  isPlayingRain={isPlayingDioramaRain}
                  onToggleRain={() => setIsPlayingDioramaRain((p) => !p)}
                  hasActiveSimulation={flowStep === 'resultado' && Boolean(activeRun)}
                  selectedPoint={selectedPoint}
                  onPointInspect={handleMapClick}
                  dailyRainContext={dailyRainContext}
                />
              </Suspense>

              {/* Botón flotante móvil para desplegar la hoja inferior cuando está plegada */}
              {isMobile && sheetSnap === 'collapsed' && (
                <div
                  style={{
                    position: 'absolute',
                    bottom: 84,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    zIndex: 50,
                  }}
                >
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setSheetSnap('half')}
                  >
                    {flowStep === 'resultado' ? 'Ver resultados y capas ↑' : 'Continuar configuración ↑'}
                  </Button>
                </div>
              )}

              {/* Punto consultado flotante */}
              {selectedPoint && (
                <div
                  style={{
                    position: 'absolute',
                    bottom: 20,
                    right: 20,
                    backgroundColor: '#FFFFFF',
                    border: 'var(--border-width) solid var(--line)',
                    borderRadius: 'var(--radius-card)',
                    padding: 14,
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
                    zIndex: 20,
                    maxWidth: 280,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <strong style={{ fontSize: 13 }}>Punto consultado</strong>
                    <button
                      type="button"
                      onClick={() => setSelectedPoint(null)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink-2)', display: 'inline-flex', alignItems: 'center' }}
                      aria-label="Cerrar detalle de punto"
                    >
                      <Icon name="x" size={14} />
                    </button>
                  </div>
                  <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 4, color: 'var(--ink-2)' }}>
                    <div>Altura: <strong style={{ color: 'var(--ink)' }}>{selectedPoint.elevation_m?.toFixed(1) ?? '—'} m</strong></div>
                    <div>Pendiente: <strong style={{ color: 'var(--ink)' }}>{selectedPoint.slope_pct?.toFixed(1) ?? '—'} %</strong></div>
                    <div>Escurre hacia: <strong style={{ color: 'var(--ink)' }}>{selectedPoint.d8_direction ?? '—'}</strong></div>
                    {selectedPoint.agronomic_zone_label && (
                      <div>Ambiente: <strong style={{ color: 'var(--ink)' }}>{selectedPoint.agronomic_zone_label}</strong></div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ width: '100%', height: '100%', position: 'relative' }}>
              <Suspense
                fallback={
                  <div
                    style={{
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--ink-2)',
                      fontSize: 13,
                    }}
                  >
                    Cargando mapa 2D...
                  </div>
                }
              >
                <TerrainScene3D
                  field={activeField}
                  mesh={mesh}
                  hydrology={hydrology}
                  observations={[]}
                  particlePaths={[]}
                  showParticles={false}
                  transitFraction={0}
                  viewMode="2d"
                  exaggeration={exaggeration}
                  layers={{
                    basemap: 'satellite',
                    surfaceColor: 'elevation',
                    mesh3d: false,
                    wireframe: false,
                    boundary: true,
                    contours: true,
                    drainageNetwork: true,
                    depressionsAndOutlets: true,
                  }}
                  interactionMode="inspect"
                  profileDraft={[]}
                  selectedPoint={selectedPoint}
                  onMapClick={handleMapClick}
                  onCursorMove={() => {}}
                />
              </Suspense>
            </div>
          )}
        </main>
      </div>

      {/* Modal para dibujar lote en el mapa */}
      <Suspense fallback={null}>
        <PolygonMapDrawer
          isOpen={isMapDrawerOpen}
          initialCenter={activeField?.centroid ?? [-66.085, -33.128]}
          onClose={() => setIsMapDrawerOpen(false)}
          onConfirmPolygon={async (name, file) => {
            await handleFullImportAndSimulate(file, name)
          }}
        />
      </Suspense>

      {/* Modal de las 8 herramientas agronómicas (SDD-002 sección 8.4) */}
      {isToolkitModalOpen && (
        <div className="toolkit-modal-overlay" role="dialog" aria-modal="true">
          <div className="toolkit-modal-container">
            <div className="toolkit-modal-header">
              <h3 className="toolkit-modal-title">
                Las 8 Herramientas Agronómicas para {activeField?.name}
              </h3>
              <Button
                variant="text"
                size="sm"
                onClick={() => setIsToolkitModalOpen(false)}
                aria-label="Cerrar modal"
                icon="x"
              >
                Cerrar
              </Button>
            </div>
            <div className="toolkit-modal-body">
              <Suspense
                fallback={
                  <div style={{ padding: 24, textAlign: 'center', color: 'var(--ink-2)', fontSize: 13 }}>
                    Cargando panel de herramientas...
                  </div>
                }
              >
                <AgronomicToolkitPanel
                  hasTerrain={Boolean(terrain)}
                  toolkit={toolkit}
                  busy={Boolean(busy)}
                  onRun={handleRunToolkit}
                  onSelect3DLayer={(layer) => {
                    setDioramaOverlay(layer === 'erosion' ? 'erosion' : 'ndvi')
                    setIsToolkitModalOpen(false)
                  }}
                />
              </Suspense>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
