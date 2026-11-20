import { useEffect, useState } from 'react'
import {
  activateRunoffRun,
  compareRunoffScenarios,
  computeTerrainProfile,
  createFieldObservation,
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
  importCsvRainfallEvent,
  importFieldGeoJSON,
  listFieldObservations,
  listFields,
  listRainfallEvents,
  listRunoffRuns,
  loadSampleField,
  loadSampleRainfallEvent,
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
  HydrologyRunIn,
  MeshOut,
  ObservationType,
  PointOut,
  ProfileOut,
  RainfallEventManualIn,
  RainfallEventOut,
  RunoffRunIn,
  RunoffRunOut,
  RunoffTimelineOut,
  ScenarioComparisonOut,
  SoilGroup,
  TerrainOut,
} from './types/api'
import {
  type AgronomistOverlayMode,
  TerrainDiorama3D,
} from './components/TerrainDiorama3D'
import { AgroLoadingOverlay } from './components/AgroLoadingOverlay'
import { PolygonMapDrawer } from './components/PolygonMapDrawer'
import {
  type InteractionMode,
  type LayerVisibility,
  type SurfaceColorMode,
  TerrainScene3D,
} from './components/TerrainScene3D'
import { AgronomicToolkitPanel } from './components/AgronomicToolkitPanel'
import { FlowTimelinePlayer } from './components/FlowTimelinePlayer'
import { HydrologyPanel } from './components/HydrologyPanel'
import { ProfileChart } from './components/ProfileChart'
import { QualityPanel } from './components/QualityPanel'
import { RainfallRunoffPanel } from './components/RainfallRunoffPanel'

export function App() {
  const [fields, setFields] = useState<FieldOut[]>([])
  const [activeFieldId, setActiveFieldId] = useState<string | null>(null)
  const [terrain, setTerrain] = useState<TerrainOut | null>(null)
  const [mesh, setMesh] = useState<MeshOut | null>(null)
  const [hydrology, setHydrology] = useState<HydrologyOut | null>(null)
  const [rainfallEvents, setRainfallEvents] = useState<RainfallEventOut[]>([])
  const [runoffRuns, setRunoffRuns] = useState<RunoffRunOut[]>([])
  const [comparison, setComparison] = useState<ScenarioComparisonOut | null>(
    null,
  )
  const [timeline, setTimeline] = useState<RunoffTimelineOut | null>(null)
  const [timelineStep, setTimelineStep] = useState<number>(0)
  const [playing, setPlaying] = useState<boolean>(false)
  const [playSpeed, setPlaySpeed] = useState<number>(1)
  const [showParticles, setShowParticles] = useState<boolean>(true)
  const [observations, setObservations] = useState<FieldObservationOut[]>([])
  const [obsDraftType] = useState<ObservationType>('ponding')
  const [obsDraftNotes] = useState<string>(
    'Anegamiento observado tras tormenta',
  )
  const [obsDraftVal] = useState<string>('')
  const [toolkit, setToolkit] = useState<AgronomicToolkitOut | null>(null)

  // Modo principal de pantalla: 'agronomist' (Maqueta 3D satelital limpia e intuitiva) o 'gis' (Mapa GIS técnico)
  const [workspaceMode, setWorkspaceMode] = useState<'agronomist' | 'gis'>(
    'agronomist',
  )
  const [isMapDrawerOpen, setIsMapDrawerOpen] = useState<boolean>(false)
  const [dioramaOverlay, setDioramaOverlay] =
    useState<AgronomistOverlayMode>('satellite_water')
  const [isPlayingDioramaRain, setIsPlayingDioramaRain] =
    useState<boolean>(true)
  const [quickRainMm, setQuickRainMm] = useState<number>(80)
  const [quickSoilGroup, setQuickSoilGroup] = useState<SoilGroup>('B')
  const [quickAmc, setQuickAmc] = useState<AntecedentMoisture>('medium')
  const [quickCover, setQuickCover] = useState<string>('soja_maiz_sd_buena')
  const [dailyRainContext, setDailyRainContext] =
    useState<DailyRainfallContextOut | null>(null)
  const [selectedDailyDate, setSelectedDailyDate] = useState<string>('')
  const [agroToolTab, setAgroToolTab] = useState<
    | 'resumen'
    | 'erosion'
    | 'terrazas'
    | 'siembra'
    | 'balance'
    | 'anegamiento'
    | 'rotaciones'
    | 'ndvi'
    | 'heladas'
  >('resumen')

  const [sourceId, setSourceId] = useState<'copernicus_glo30' | 'upload'>(
    'copernicus_glo30',
  )
  const [bufferM, setBufferM] = useState<number>(300)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadSurfaceType, setUploadSurfaceType] = useState<
    'DTM' | 'DSM' | 'desconocido'
  >('DTM')
  const [uploadDatum, setUploadDatum] = useState<string>('EGM2008')
  const [uploadAccuracy, setUploadAccuracy] = useState<string>('')

  const [viewMode, setViewMode] = useState<'2d' | '3d'>('3d')
  const [exaggeration, setExaggeration] = useState<number>(2.5)
  const [layers, setLayers] = useState<LayerVisibility>({
    basemap: 'satellite',
    surfaceColor: 'elevation',
    mesh3d: true,
    wireframe: false,
    boundary: true,
    contours: true,
    drainageNetwork: true,
    depressionsAndOutlets: true,
  })
  const [interactionMode, setInteractionMode] =
    useState<InteractionMode>('inspect')

  const [, setCursorCoords] = useState<[number, number] | null>(
    null,
  )
  const [selectedPoint, setSelectedPoint] = useState<PointOut | null>(null)
  const [profileDraft, setProfileDraft] = useState<[number, number][]>([])
  const [profileResult, setProfileResult] = useState<ProfileOut | null>(null)

  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const activeField = fields.find((f) => f.id === activeFieldId) ?? null
  const activeRun =
    runoffRuns.find((r) => r.is_active) ?? runoffRuns[0] ?? null

  useEffect(() => {
    listFields()
      .then((list) => {
        setFields(list)
        if (list.length > 0) setActiveFieldId(list[0].id)
      })
      .catch((err: Error) => setError(err.message))
  }, [])

  useEffect(() => {
    setTerrain(null)
    setMesh(null)
    setHydrology(null)
    setRainfallEvents([])
    setRunoffRuns([])
    setComparison(null)
    setTimeline(null)
    setPlaying(false)
    setObservations([])
    setToolkit(null)
    setDailyRainContext(null)
    setSelectedDailyDate('')
    setSelectedPoint(null)
    setProfileDraft([])
    setProfileResult(null)
    if (!activeField) return
    if (!activeField.has_terrain) return

    setBusy('Cargando relieve 3D del campo y simulación de lluvia...')
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

  /** Flujo de 1 clic para el agrónomo: carga el lote, descarga el DEM 3D, calcula drenaje, lluvia y las 8 herramientas. */
  const handleQuickLoadAndSimulateField = async (
    preset: 'serrano' | 'llanura',
  ) => {
    setError(null)
    setBusy(
      preset === 'serrano'
        ? 'Cargando Lote Piedemonte Serrano (223 ha) y generando maqueta 3D con simulación de lluvia...'
        : 'Cargando Lote Agrícola #205 (199 ha) y generando maqueta 3D con simulación de lluvia...',
    )
    try {
      const imported = await loadSampleField(preset)
      const fld = imported[0]
      if (!fld) return
      if (!fld.has_terrain) {
        await processTerrain(fld.id, {
          sourceId: 'copernicus_glo30',
          bufferM: 300,
        })
      }
      if (!fld.has_hydrology) {
        await runStaticHydrology(fld.id, {
          conditioning_mode: 'fill_small',
          max_fill_depth_m: 0.35,
          max_fill_area_m2: 4500,
          mfd_exponent: 1.1,
          routing_basis: 'MFD',
        })
      }
      const ev = await loadSampleRainfallEvent(fld.id)
      const rns = await listRunoffRuns(fld.id)
      if (rns.length === 0) {
        const created = await executeRunoffRun(fld.id, {
          name: `Tormenta ${ev.total_mm} mm · Suelo B · Siembra Directa`,
          rainfall_event_id: ev.id,
          soil_group: 'B',
          cover_code: 'soja_maiz_sd_buena',
          antecedent_moisture: 'medium',
          compaction_high: false,
          lambda_ratio: 0.2,
        })
        await runHydrodynamic2DSolver(fld.id, created.id, {
          ponding_threshold_m: 0.05,
          recession_minutes: 30,
        })
      }
      await getAgronomicToolkit(fld.id).catch(() =>
        runAgronomicToolkit(fld.id, {
          soil_group: 'B',
          cover_code: 'soja_maiz_sd_buena',
          storm_precipitation_mm: 80,
          crop_code: 'maiz_temprano',
          environment_zone: 'media_loma',
        }),
      )
      const all = await listFields()
      setFields(all)
      setActiveFieldId(fld.id)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  /** Simulación rápida de lluvia para el agrónomo en 1 clic. */
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
      const ev = await createManualRainfallEvent(activeField.id, {
        name: `Lluvia ${mm} mm`,
        total_mm: mm,
        source_type: 'manual',
      })
      const created = await executeRunoffRun(activeField.id, {
        name: `${mm} mm · Suelo ${soil} · ${
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
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  /** Simulación de la lluvia diaria estimada (NASA POWER ~55 km). */
  const handleSimulateDailyRain = async (dateStr?: string) => {
    if (!activeField) return
    const target =
      dateStr || selectedDailyDate || dailyRainContext?.selected_day?.date
    if (!target) return
    setError(null)
    setBusy(`Consultando lluvia estimada NASA POWER para el día ${target}...`)
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
    } catch (err) {
      setError((err as Error).message)
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

  /** Importa un polígono (dibujado en el mapa o subido por archivo) y ejecuta automáticamente todo el flujo 3D + lluvia + agronomía. */
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
          `Paso 2/4: Descargando relieve satelital 3D Copernicus (30 m) para ${fld.name} (${fld.area_ha.toFixed(1)} ha)...`,
        )
        await processTerrain(fld.id, {
          sourceId: 'copernicus_glo30',
          bufferM: 300,
        })
        setBusy(
          'Paso 3/4: Calculando pendientes, vaguadas, red de escurrimiento y simulación de lluvia en 3D...',
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
        setBusy(
          'Paso 4/4: Generando diagnóstico agronómico INTA / NASA POWER / Sentinel-2...',
        )
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
      if (fld) setActiveFieldId(fld.id)
      setIsMapDrawerOpen(false)
    } catch (err) {
      setError((err as Error).message)
      throw err
    } finally {
      setBusy(null)
    }
  }

  const handleProcessTerrain = async () => {
    if (!activeField) return
    setError(null)
    setBusy(
      sourceId === 'copernicus_glo30'
        ? 'Descargando ventana COG Copernicus GLO-30 (30 m) y reproyectando a UTM...'
        : 'Procesando GeoTIFF subido y reproyectando a UTM...',
    )
    try {
      const t = await processTerrain(activeField.id, {
        sourceId,
        bufferM,
        file: sourceId === 'upload' ? uploadFile : null,
        surfaceType: uploadSurfaceType,
        verticalDatum: uploadDatum,
        verticalAccuracyM: uploadAccuracy,
      })
      const m = await getTerrainMesh(activeField.id)
      setTerrain(t)
      setMesh(m)
      setHydrology(null)
      const all = await listFields()
      setFields(all)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleRunHydrology = async (params: HydrologyRunIn) => {
    if (!activeField) return
    setError(null)
    setBusy(
      'Calculando acondicionamiento selectivo, direcciones D8, acumulación MFD, depresiones y red de drenaje...',
    )
    try {
      const h = await runStaticHydrology(activeField.id, params)
      const m = await getTerrainMesh(activeField.id)
      setHydrology(h)
      setMesh(m)
      setLayers((prev) => ({
        ...prev,
        surfaceColor: 'mfd',
        contours: true,
        drainageNetwork: true,
        depressionsAndOutlets: true,
      }))
      const all = await listFields()
      setFields(all)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleCreateManualEvent = async (payload: RainfallEventManualIn) => {
    if (!activeField) return
    setError(null)
    setBusy('Registrando evento de lluvia manual...')
    try {
      await createManualRainfallEvent(activeField.id, payload)
      setRainfallEvents(await listRainfallEvents(activeField.id))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleLoadSampleEvent = async () => {
    if (!activeField) return
    setError(null)
    setBusy('Importando tormenta CSV de muestra (80 mm · 15 min)...')
    try {
      await loadSampleRainfallEvent(activeField.id)
      setRainfallEvents(await listRainfallEvents(activeField.id))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleImportCsvEvent = async (
    file: File,
    name: string,
    sourceType: string,
  ) => {
    if (!activeField) return
    setError(null)
    setBusy(`Validando serie temporal CSV (${file.name})...`)
    try {
      await importCsvRainfallEvent(activeField.id, file, name, sourceType)
      setRainfallEvents(await listRainfallEvents(activeField.id))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleRunRunoff = async (payload: RunoffRunIn) => {
    if (!activeField) return
    setError(null)
    setBusy('Calculando escorrentía NRCS Curve Number y carga espacial MFD...')
    try {
      const created = await executeRunoffRun(activeField.id, payload)
      const [h, m, rns, tl, all] = await Promise.all([
        getStaticHydrology(activeField.id),
        getTerrainMesh(activeField.id),
        listRunoffRuns(activeField.id),
        getRunoffTimeline(activeField.id, created.id).catch(() => null),
        listFields(),
      ])
      setHydrology(h)
      setMesh(m)
      setRunoffRuns(rns)
      setTimeline(tl)
      setTimelineStep(tl?.peak_step_index ?? 0)
      setFields(all)
      setLayers((prev) => ({ ...prev, surfaceColor: 'runoff' }))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleActivateRunoff = async (runId: string) => {
    if (!activeField) return
    setError(null)
    setBusy('Activando escenario de escorrentía en la malla 3D...')
    try {
      await activateRunoffRun(activeField.id, runId)
      const [m, rns, tl] = await Promise.all([
        getTerrainMesh(activeField.id),
        listRunoffRuns(activeField.id),
        getRunoffTimeline(activeField.id, runId).catch(() => null),
      ])
      setMesh(m)
      setRunoffRuns(rns)
      setTimeline(tl)
      setTimelineStep(tl?.peak_step_index ?? 0)
      setLayers((prev) => ({ ...prev, surfaceColor: 'runoff' }))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleCompareScenarios = async (runA: string, runB: string) => {
    if (!activeField) return
    setError(null)
    try {
      const comp = await compareRunoffScenarios(activeField.id, runA, runB)
      setComparison(comp)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const handleRun2DSolver = async (runId: string) => {
    if (!activeField) return
    setError(null)
    setBusy(
      'Ejecutando Solver Hidrodinámico 2D de onda difusiva (Manning) y Zonificación RotaTerra...',
    )
    try {
      await runHydrodynamic2DSolver(activeField.id, runId, {
        ponding_threshold_m: 0.05,
        recession_minutes: 30,
      })
      const [m, rns] = await Promise.all([
        getTerrainMesh(activeField.id),
        listRunoffRuns(activeField.id),
      ])
      setMesh(m)
      setRunoffRuns(rns)
      setLayers((prev) => ({ ...prev, surfaceColor: 'water_depth' }))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleRunToolkit = async (params: AgronomicToolkitIn) => {
    if (!activeField) return
    setError(null)
    setBusy(
      'Calculando 8 herramientas: Erosión USLE, Balance Hídrico NASA POWER, Anegamiento por fecha real, Terrazas a nivel, Siembra INTA, Rotaciones 3a, Vigor NDVI y Heladas...',
    )
    try {
      const tk = await runAgronomicToolkit(activeField.id, params)
      const [h, m, all] = await Promise.all([
        getStaticHydrology(activeField.id),
        getTerrainMesh(activeField.id),
        listFields(),
      ])
      setToolkit(tk)
      setHydrology(h)
      setMesh(m)
      setFields(all)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const handleMapClick = async (lon: number, lat: number) => {
    if (!activeField || !terrain) return
    setError(null)
    if (interactionMode === 'inspect' || workspaceMode === 'agronomist') {
      try {
        const pt = await queryTerrainPoint(activeField.id, lon, lat)
        setSelectedPoint(pt)
      } catch (err) {
        setError((err as Error).message)
      }
      return
    }

    if (interactionMode === 'observe') {
      try {
        await createFieldObservation(activeField.id, {
          observation_type: obsDraftType,
          lon,
          lat,
          notes: obsDraftNotes.trim() || 'Observación de campo',
          value: obsDraftVal.trim() !== '' ? Number(obsDraftVal) : null,
          units: obsDraftVal.trim() !== '' ? 'm' : null,
        })
        setObservations(await listFieldObservations(activeField.id))
      } catch (err) {
        setError((err as Error).message)
      }
      return
    }

    const next: [number, number][] = [...profileDraft, [lon, lat]]
    setProfileDraft(next)
    if (next.length >= 2) {
      try {
        const pf = await computeTerrainProfile(activeField.id, next)
        setProfileResult(pf)
      } catch (err) {
        setError((err as Error).message)
      }
    }
  }

  // Semáforo diagnóstico para el agrónomo
  const runoffQ = activeRun?.cn_result.runoff_q_mm ?? 0
  const erosionMean = toolkit?.erosion_usle.mean_soil_loss_t_ha ?? 0
  const lowZonePct =
    (activeRun?.agronomic_zonation ?? hydrology?.agronomic_zonation)?.zones.find(
      (z) => z.zone_id === 4,
    )?.percentage_of_field ?? 12.0

  let badgeStatus: { level: 'ok' | 'warn' | 'crit'; text: string } = {
    level: 'warn',
    text: 'Requiere revisión en bajos y vías de agua',
  }
  if (runoffQ >= 42 || erosionMean >= 2.2) {
    badgeStatus = {
      level: 'crit',
      text: 'Riesgo Hídrico / Erosivo Alto — Intervenir con cobertura o terrazas',
    }
  } else if (runoffQ < 12 && erosionMean < 0.4) {
    badgeStatus = {
      level: 'ok',
      text: 'Comportamiento Hidrológico Estable — Buena infiltración',
    }
  }

  const rainFactor = Math.min(1.8, Math.max(0.2, quickRainMm / 70.0))

  return (
    <div className="app-shell">
      {/* Pantalla de Carga Inmersiva con Estilo Agrícola y Sabiduría Técnica */}
      <AgroLoadingOverlay
        message={busy}
        onDismiss={() => setBusy(null)}
        fieldName={activeField?.name}
        fieldAreaHa={activeField?.area_ha}
      />

      <header className="topbar">
        <div className="brand">
          <div className="brand-meta-row">
            <span className="badge-phase">ROTATERRA 3D · AGRO-HIDROLOGÍA</span>
            <span className="badge-smn-status">🛰️ NASA POWER (~55 km)</span>
          </div>
          <h1>
            Simulador 3D de Lluvia, Escurrimiento y Planificación Agronómica
          </h1>
        </div>

        <div className="topbar-controls">
          <div className="segmented" role="group" aria-label="Modo de interfaz">
            <button
              className={workspaceMode === 'agronomist' ? 'active' : ''}
              onClick={() => setWorkspaceMode('agronomist')}
            >
              🌱 Vista Maqueta 3D Agrónomo
            </button>
            <button
              className={workspaceMode === 'gis' ? 'active' : ''}
              onClick={() => setWorkspaceMode('gis')}
            >
              🗺️ Mapa GIS Regional / Técnico
            </button>
          </div>

          <button
            type="button"
            className="btn-topbar-draw"
            onClick={() => setIsMapDrawerOpen(true)}
            disabled={Boolean(busy)}
          >
            ✏️ Dibujar mi Lote en el Mapa
          </button>

          <label className="exag-control">
            <span>Relieve 3D:</span>
            <select
              value={exaggeration}
              onChange={(e) => setExaggeration(Number(e.target.value))}
            >
              <option value={1}>1× (plano real)</option>
              <option value={2}>2× (moderado)</option>
              <option value={2.5}>2,5× (maqueta ideal)</option>
              <option value={3.5}>3,5× (relieve pronunciado)</option>
              <option value={5}>5× (máximo contraste)</option>
            </select>
          </label>

          {activeField && terrain && (
            <div className="export-links">
              <a
                className="btn-ghost"
                href={exportGeoJsonUrl(activeField.id)}
                download
              >
                ⬇ Descargar Capas GIS
              </a>
              <a
                className="btn-ghost"
                href={exportReportUrl(activeField.id)}
                target="_blank"
                rel="noreferrer"
              >
                📄 Informe para el Productor
              </a>
            </div>
          )}
        </div>
      </header>

      {workspaceMode === 'agronomist' ? (
        <div className="agro-layout">
          {/* Columna izquierda: Selección de Lote + Simulador simple de Lluvia y Manejo */}
          <aside className="agro-sidebar">
            <section className="agro-card agro-card-highlight">
              <div className="step-header-row">
                <span className="step-num-badge">PASO 1</span>
                <h3>Ubicá o Dibujá tu Campo</h3>
              </div>
              <p className="agro-help">
                Marcá las esquinas de tu terreno directamente en el mapa
                satelital con polígonos, o probá un campo real precargado:
              </p>
              <div className="btn-stack">
                <button
                  type="button"
                  className="btn-agro-draw-polygon"
                  onClick={() => setIsMapDrawerOpen(true)}
                  disabled={Boolean(busy)}
                >
                  ✏️ Dibujar mi Terreno con Polígonos en el Mapa
                </button>
                <button
                  className="btn-agro-primary"
                  onClick={() => handleQuickLoadAndSimulateField('serrano')}
                  disabled={Boolean(busy)}
                >
                  ⛰️ Ejemplo 1: Lote Piedemonte Serrano (223 ha · Alto relieve)
                </button>
                <button
                  className="btn-agro-secondary"
                  onClick={() => handleQuickLoadAndSimulateField('llanura')}
                  disabled={Boolean(busy)}
                >
                  🌾 Ejemplo 2: Lote Agrícola #205 (199 ha · Llanura ondulada)
                </button>
                <label className="btn-agro-outline">
                  📂 Subir archivo de mi lote (.kml, .kmz, .geojson, .zip)
                  <input
                    type="file"
                    accept=".geojson,.json,.kml,.kmz,.zip"
                    onChange={handleImportGeoJSON}
                    hidden
                  />
                </label>
              </div>

              {fields.length > 1 && (
                <label className="field-label" style={{ marginTop: 10 }}>
                  Mis lotes analizados ({fields.length})
                  <select
                    value={activeFieldId ?? ''}
                    onChange={(e) => setActiveFieldId(e.target.value)}
                  >
                    {fields.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name} ({f.area_ha.toFixed(1)} ha)
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </section>

            <section className="agro-card">
              <div className="step-header-row">
                <span className="step-num-badge">PASO 2</span>
                <h3>Simulá Lluvia y Manejo</h3>
              </div>
              <p className="agro-help">
                Simulá la escorrentía a partir de lluvia diaria estimada (NASA POWER ~55 km) o probá escenarios de diseño agronómico.
              </p>

              {/* Sección de Lluvia Diaria Estimada: NASA POWER ~55 km */}
              <div className="smn-daily-section">
                <div className="smn-section-header">
                  <div className="smn-badge-title">
                    <span className="smn-flag">🛰️</span>
                    <strong>Lluvia Diaria Estimada (NASA POWER · ~55 km)</strong>
                  </div>
                  {dailyRainContext?.nearest_smn_station && (
                    <span className="smn-station-tag" title="Referencia geográfica sin datos conectados">
                      Estación SMN más cercana (referencia, sin datos conectados): {dailyRainContext.nearest_smn_station.name} ({dailyRainContext.nearest_smn_station.distance_km} km)
                    </span>
                  )}
                </div>

                <p className="smn-desc">
                  Datos obtenidos de <strong>NASA POWER (MERRA-2 / GPCP · ~55 km)</strong>. La estación SMN se informa únicamente como referencia geográfica sin conexión de datos. <em>Lluvia regional estimada (~55 km), no es la medición de su campo.</em>
                </p>

                {dailyRainContext?.recent_rainy_days &&
                  dailyRainContext.recent_rainy_days.length > 0 && (
                    <label className="field-label" style={{ marginBottom: 6 }}>
                      Días con lluvia registrados en este campo:
                      <select
                        value={selectedDailyDate}
                        onChange={(e) => {
                          setSelectedDailyDate(e.target.value)
                          handleSimulateDailyRain(e.target.value)
                        }}
                        disabled={Boolean(busy)}
                      >
                        {dailyRainContext.recent_rainy_days.map((rd) => (
                          <option key={rd.date} value={rd.date}>
                            📅 {rd.date} · {rd.precipitation_mm.toFixed(1)} mm ({rd.antecedent_moisture_amc === 'wet' ? 'Suelo saturado' : rd.antecedent_moisture_amc === 'medium' ? 'Humedad media' : 'Suelo seco'})
                          </option>
                        ))}
                      </select>
                    </label>
                  )}

                <div className="daily-date-picker-row">
                  <label className="field-label" style={{ flex: 1 }}>
                    O elegí cualquier fecha específica:
                    <input
                      type="date"
                      value={selectedDailyDate}
                      onChange={(e) => setSelectedDailyDate(e.target.value)}
                      disabled={Boolean(busy)}
                    />
                  </label>
                  <button
                    type="button"
                    className="btn-primary smn-simulate-btn"
                    onClick={() => handleSimulateDailyRain(selectedDailyDate)}
                    disabled={Boolean(busy) || !selectedDailyDate}
                  >
                    🌧️ Simular lluvia estimada
                  </button>
                </div>

                {dailyRainContext?.selected_day && (
                  <div className="daily-stats-card">
                    <div className="daily-stat-item">
                      <span className="daily-stat-label">Lluvia del día</span>
                      <strong className="daily-stat-val rain-val">
                        {dailyRainContext.selected_day.precipitation_mm.toFixed(1)} mm
                      </strong>
                    </div>
                    <div className="daily-stat-item">
                      <span className="daily-stat-label">Humedad previa 5d</span>
                      <strong className="daily-stat-val">
                        {dailyRainContext.selected_day.prior_5d_rain_mm.toFixed(1)} mm ({dailyRainContext.selected_day.antecedent_moisture_amc.toUpperCase()})
                      </strong>
                    </div>
                    <div className="daily-stat-item">
                      <span className="daily-stat-label">Temperatura</span>
                      <strong className="daily-stat-val">
                        {dailyRainContext.selected_day.tmin_c}° a {dailyRainContext.selected_day.tmax_c}°C
                      </strong>
                    </div>
                  </div>
                )}
              </div>

              <span className="subhead" style={{ marginTop: 12 }}>Elegir intensidad de lluvia de diseño:</span>
              <div className="pill-row">
                {[
                  { mm: 30, label: '🌧️ 30 mm (Suave)' },
                  { mm: 80, label: '⛈️ 80 mm (Fuerte)' },
                  { mm: 130, label: '🌊 130 mm (Temporal)' },
                ].map((p) => (
                  <button
                    key={p.mm}
                    className={
                      quickRainMm === p.mm ? 'pill-btn active' : 'pill-btn'
                    }
                    onClick={() => handleQuickSimulateRain(p.mm)}
                    disabled={Boolean(busy)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>

              <label className="field-label" style={{ marginTop: 10 }}>
                ¿Cómo estaba el suelo antes de llover?
                <select
                  value={quickAmc}
                  onChange={(e) =>
                    handleQuickSimulateRain(
                      undefined,
                      e.target.value as AntecedentMoisture,
                    )
                  }
                  disabled={Boolean(busy)}
                >
                  <option value="dry">
                    Suelo seco (absorbe mucha más agua al inicio)
                  </option>
                  <option value="medium">
                    Humedad normal (condición media de campaña)
                  </option>
                  <option value="wet">
                    Suelo ya húmedo por lluvias previas (escurre rápido)
                  </option>
                </select>
              </label>

              <label className="field-label">
                ¿Qué cobertura tiene hoy la superficie del lote?
                <select
                  value={quickCover}
                  onChange={(e) =>
                    handleQuickSimulateRain(
                      undefined,
                      undefined,
                      e.target.value,
                    )
                  }
                  disabled={Boolean(busy)}
                >
                  <option value="soja_maiz_sd_buena">
                    Siembra Directa con buen rastrojo (&gt;30% cubierto)
                  </option>
                  <option value="cultivo_cobertura_vicia_centeno">
                    Cultivo de Servicio activo (Vicia + Centeno)
                  </option>
                  <option value="trigo_cereal_invierno_sd">
                    Trigo / Cereal de invierno denso en SD
                  </option>
                  <option value="pastura_pradera_buena">
                    Pastura / Verdeo en buena condición
                  </option>
                  <option value="barbecho_con_rastrojo">
                    Barbecho químico con rastrojo
                  </option>
                  <option value="soja_maiz_convencional">
                    Labranza convencional / Poca cobertura
                  </option>
                  <option value="barbecho_suelo_desnudo">
                    Suelo descubierto sin rastrojo (mayor riesgo)
                  </option>
                </select>
              </label>

              <label className="field-label">
                Tipo de suelo predominante
                <select
                  value={quickSoilGroup}
                  onChange={(e) =>
                    handleQuickSimulateRain(
                      undefined,
                      undefined,
                      undefined,
                      e.target.value as SoilGroup,
                    )
                  }
                  disabled={Boolean(busy)}
                >
                  <option value="A">
                    Suelo Arenoso / Franco-arenoso (infiltra rápido)
                  </option>
                  <option value="B">
                    Suelo Franco / Franco-limoso (infiltración moderada)
                  </option>
                  <option value="C">
                    Suelo Franco-arcilloso (infiltración lenta)
                  </option>
                  <option value="D">
                    Suelo Arcilloso pesado / Bajo con napa (infiltra muy poco)
                  </option>
                </select>
              </label>
            </section>

            {activeRun && (
              <section className="agro-card">
                <div className="step-header-row">
                  <span className="step-num-badge">RESUMEN</span>
                  <h3>¿Adónde va el agua de lluvia?</h3>
                </div>
                {(() => {
                  const totalRain = Math.max(
                    1,
                    activeRun.cn_result.precipitation_mm,
                  )
                  const infilPct = Math.min(
                    100,
                    Math.max(
                      0,
                      (activeRun.cn_result.total_retention_losses_mm /
                        totalRain) *
                        100,
                    ),
                  )
                  const runoffPct = Math.max(0, 100 - infilPct)
                  return (
                    <div className="water-split-bar-box">
                      <div className="water-split-labels">
                        <span className="text-emerald">
                          🌱 Entra al suelo: {infilPct.toFixed(0)}%
                        </span>
                        <span className="text-sky">
                          🌊 Escurre: {runoffPct.toFixed(0)}%
                        </span>
                      </div>
                      <div className="water-split-track">
                        <div
                          className="water-split-fill-infil"
                          style={{ width: `${infilPct}%` }}
                        />
                        <div
                          className="water-split-fill-runoff"
                          style={{ width: `${runoffPct}%` }}
                        />
                      </div>
                    </div>
                  )
                })()}
                <div className="kpi-cards">
                  <div className="kpi-box kpi-green">
                    <span className="kpi-label">Agua que entra al suelo</span>
                    <strong className="kpi-val">
                      {activeRun.cn_result.total_retention_losses_mm.toFixed(1)}{' '}
                      mm
                    </strong>
                    <span className="kpi-sub">
                      Queda disponible o infiltra en el perfil
                    </span>
                  </div>
                  <div className="kpi-box kpi-blue">
                    <span className="kpi-label">Agua que escurre</span>
                    <strong className="kpi-val">
                      {activeRun.cn_result.runoff_q_mm.toFixed(1)} mm
                    </strong>
                    <span className="kpi-sub">
                      {(
                        activeRun.spatial_summary.field_runoff_generated_m3 /
                        1000
                      ).toFixed(1)}{' '}
                      mil m³ corren por pendiente
                    </span>
                  </div>
                  <div className="kpi-box kpi-amber">
                    <span className="kpi-label">Bajos que acumulan agua</span>
                    <strong className="kpi-val">
                      {hydrology?.summary.total_depression_area_in_field_ha.toFixed(
                        1,
                      ) ?? '3.9'}{' '}
                      ha
                    </strong>
                    <span className="kpi-sub">
                      Retienen hasta{' '}
                      {hydrology?.summary.total_depression_volume_in_field_m3.toFixed(
                        0,
                      ) ?? '8000'}{' '}
                      m³
                    </span>
                  </div>
                  <div className="kpi-box kpi-purple">
                    <span className="kpi-label">Espera para maquinaria</span>
                    <strong className="kpi-val">
                      ~
                      {(
                        activeRun.agronomic_zonation ??
                        hydrology?.agronomic_zonation
                      )?.trafficability.estimated_wait_days_low_ground ??
                        3.5}{' '}
                      días
                    </strong>
                    <span className="kpi-sub">
                      Para tener piso en los bajos (
                      {(
                        activeRun.agronomic_zonation ??
                        hydrology?.agronomic_zonation
                      )?.trafficability.estimated_wait_days_high_ground ?? 1.3}{' '}
                      d en lomas)
                    </span>
                  </div>
                </div>
              </section>
            )}
          </aside>

          {/* Centro: Tarjeta Maqueta 3D Satelital estilo CASO #1327 */}
          <main className="agro-center">
            {busy && <div className="status-toast">{busy}</div>}
            {error && (
              <div className="error-toast" role="alert">
                <span>{error}</span>
                <button onClick={() => setError(null)}>✕</button>
              </div>
            )}

            <div className="showcase-card">
              <div className="showcase-header">
                <div className="showcase-title-block">
                  <span className="showcase-kicker">
                    SIMULACIÓN TOPOGRÁFICA E HIDROLÓGICA 3D
                  </span>
                  <h2>{activeField ? activeField.name : 'Cargando lote...'}</h2>
                  {activeField && terrain && (
                    <div className="showcase-meta-pills">
                      <span>📍 Provincia de San Luis, Argentina</span>
                      <span>
                        📐 {activeField.area_ha.toFixed(1)} ha (
                        {(activeField.area_ha / 100).toFixed(2)} km²)
                      </span>
                      <span>
                        ⛰️ Cotas:{' '}
                        {terrain.quality.elevation_field.min?.toFixed(0)} a{' '}
                        {terrain.quality.elevation_field.max?.toFixed(0)} m
                        s.n.m. (desnivel{' '}
                        {terrain.quality.elevation_field.range?.toFixed(1)} m)
                      </span>
                    </div>
                  )}
                </div>

                <div className="showcase-layer-bar">
                  {(
                    [
                      ['satellite_water', '🛰️ Agua Corriendo'],
                      ['waterlogging', '💧 Donde se Encharca'],
                      ['environments', '🌱 Lomas y Bajos'],
                      ['erosion', '⚠️ Pérdida de Suelo'],
                      ['ndvi', '🌿 Vigor Cultivo (NDVI)'],
                    ] as const
                  ).map(([mode, label]) => (
                    <button
                      key={mode}
                      className={
                        dioramaOverlay === mode
                          ? 'overlay-pill active'
                          : 'overlay-pill'
                      }
                      onClick={() => setDioramaOverlay(mode)}
                    >
                      {label}
                    </button>
                  ))}
                  <button
                    className={
                      isPlayingDioramaRain
                        ? 'overlay-pill rain-toggle active'
                        : 'overlay-pill rain-toggle'
                    }
                    onClick={() => setIsPlayingDioramaRain((p) => !p)}
                  >
                    {isPlayingDioramaRain
                      ? '⏸ Pausar lluvia 3D'
                      : '▶ Animar lluvia 3D'}
                  </button>
                  <button
                    type="button"
                    className="overlay-pill draw-lot-pill"
                    onClick={() => setIsMapDrawerOpen(true)}
                  >
                    ✏️ Dibujar mi lote en mapa
                  </button>
                </div>
                <div className="showcase-layer-explainer">
                  {dioramaOverlay === 'satellite_water' &&
                    '💡 Estás viendo: La imagen del terreno 3D y las líneas celestes por donde corre y se junta el agua de lluvia.'}
                  {dioramaOverlay === 'waterlogging' &&
                    '💡 Estás viendo: En azul intenso los bajos donde el agua queda acumulada y tarda más días en dar piso.'}
                  {dioramaOverlay === 'environments' &&
                    '💡 Estás viendo: El campo dividido en Loma alta (dorado), Media loma (verde), Vía de agua (naranja) y Bajo (azul).'}
                  {dioramaOverlay === 'erosion' &&
                    '💡 Estás viendo: En naranja y rojo las pendientes donde la lluvia arrastra más tierra fértil (riesgo de cárcavas).'}
                  {dioramaOverlay === 'ndvi' &&
                    '💡 Estás viendo: El índice de vigor satelital Sentinel-2 (verde = cultivo denso y activo; ocre = menor cobertura).'}
                </div>
              </div>

              <div className="showcase-diorama-stage">
                <TerrainDiorama3D
                  field={activeField}
                  mesh={mesh}
                  overlayMode={dioramaOverlay}
                  exaggeration={exaggeration}
                  rainIntensityFactor={rainFactor}
                  showBoundary={true}
                  showContours={false}
                  isPlayingRain={isPlayingDioramaRain}
                  selectedPoint={selectedPoint}
                  onPointInspect={handleMapClick}
                  dailyRainContext={dailyRainContext}
                />

                {selectedPoint && (
                  <div className="floating-point-card">
                    <div className="card-header">
                      <strong>📍 Punto consultado en el lote</strong>
                      <button
                        className="btn-ghost"
                        onClick={() => setSelectedPoint(null)}
                      >
                        ✕
                      </button>
                    </div>
                    <div className="floating-point-grid">
                      <span>
                        Altura:{' '}
                        <strong>
                          {selectedPoint.elevation_m?.toFixed(1) ?? '—'} m
                        </strong>
                      </span>
                      <span>
                        Pendiente:{' '}
                        <strong>
                          {selectedPoint.slope_pct?.toFixed(2) ?? '—'} %
                          {selectedPoint.slope_deg != null && ` (${selectedPoint.slope_deg.toFixed(1)}°)`}
                        </strong>
                      </span>
                      <span>
                        Escurre hacia:{' '}
                        <strong>
                          {selectedPoint.d8_direction ?? '—'}
                        </strong>
                      </span>
                      <span>
                        Aporte aguas arriba:{' '}
                        <strong>
                          {selectedPoint.mfd_area_ha?.toFixed(2) ?? '—'} ha
                        </strong>
                      </span>
                      {selectedPoint.agronomic_zone_label && (
                        <span style={{ gridColumn: '1 / -1' }}>
                          Ambiente:{' '}
                          <strong>{selectedPoint.agronomic_zone_label}</strong>
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="showcase-footer">
                <div className={`status-pill status-${badgeStatus.level}`}>
                  <span className="status-dot" />
                  <strong>{badgeStatus.text}</strong>
                </div>
                <p className="showcase-headline">
                  ANTES DE SEMBRAR O INVERTIR EN LABORES:{' '}
                  <strong>conocé cómo se comporta tu lote cuando llueve</strong>
                </p>
                {activeRun && (
                  <p className="showcase-subline">
                    Ante una lluvia de{' '}
                    <strong>
                      {activeRun.cn_result.precipitation_mm.toFixed(0)} mm
                    </strong>
                    , las líneas celestes muestran por dónde se concentra el
                    agua superficial hacia los bajos ({lowZonePct.toFixed(1)} %
                    de la superficie del lote) y los puntos de salida.
                  </p>
                )}
              </div>
            </div>
          </main>

          {/* Columna derecha: Las 8 Herramientas Agronómicas explicadas de forma simple y accionable */}
          <aside className="agro-sidebar">
            <section className="agro-card">
              <div className="step-header-row">
                <span className="step-num-badge">PASO 3</span>
                <h3>Decisiones para tu Lote</h3>
              </div>
              <p className="agro-help">
                Elegí qué recomendación querés consultar según el relieve 3D,
                clima NASA y tablas de INTA:
              </p>

              <div className="agro-tool-grid">
                {(
                  [
                    ['resumen', '📋 Resumen del Lote'],
                    ['siembra', '🌱 Siembra y Fertiliz.'],
                    ['erosion', '⚠️ Erosión y Cárcavas'],
                    ['terrazas', '🚜 Curvas y Terrazas'],
                    ['balance', '💧 Agua Mes a Mes'],
                    ['anegamiento', '📅 Lluvias Reales'],
                    ['rotaciones', '🔄 Rotación 3 Años'],
                    ['ndvi', '🛰️ Vigor Satelital'],
                    ['heladas', '❄️ Fechas sin Heladas'],
                  ] as const
                ).map(([k, label]) => (
                  <button
                    key={k}
                    className={
                      agroToolTab === k ? 'agro-tab-btn active' : 'agro-tab-btn'
                    }
                    onClick={() => {
                      setAgroToolTab(k)
                      if (k === 'erosion') setDioramaOverlay('erosion')
                      else if (k === 'ndvi') setDioramaOverlay('ndvi')
                      else if (k === 'anegamiento')
                        setDioramaOverlay('waterlogging')
                      else if (k === 'siembra' || k === 'resumen')
                        setDioramaOverlay('environments')
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {!toolkit ? (
                <button
                  className="btn-agro-primary full-width"
                  style={{ marginTop: 10 }}
                  onClick={() =>
                    handleRunToolkit({
                      soil_group: quickSoilGroup,
                      cover_code: quickCover,
                      storm_precipitation_mm: quickRainMm,
                      crop_code: 'maiz_temprano',
                      environment_zone: 'media_loma',
                    })
                  }
                  disabled={!terrain || Boolean(busy)}
                >
                  🚀 Calcular las 8 Herramientas Agronómicas
                </button>
              ) : (
                <div className="agro-panel-body">
                  {agroToolTab === 'resumen' && (
                    <div className="agro-explain">
                      <h4>¿Cómo se divide este campo según el agua?</h4>
                      <p>
                        El relieve divide tu lote en{' '}
                        <strong>4 ambientes productivos</strong> con distinto
                        comportamiento cuando llueve:
                      </p>
                      {(
                        activeRun?.agronomic_zonation ??
                        hydrology?.agronomic_zonation
                      )?.zones.map((z) => (
                        <div key={z.zone_id} className="env-item">
                          <div className="env-item-head">
                            <strong>{z.label}</strong>
                            <span>
                              {z.area_ha.toFixed(1)} ha (
                              {z.percentage_of_field.toFixed(0)} %)
                            </span>
                          </div>
                          <p>{z.management_guideline}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {agroToolTab === 'erosion' && (
                    <div className="agro-explain">
                      <h4>1. ¿Cuánto suelo se pierde por escurrimiento?</h4>
                      <p>
                        Con una tormenta de{' '}
                        <strong>{quickRainMm} mm</strong>, el agua que corre por
                        las pendientes arrastra suelo fértil (fórmula USLE):
                      </p>
                      <div className="kpi-cards">
                        <div className="kpi-box kpi-amber">
                          <span className="kpi-label">Pérdida promedio</span>
                          <strong className="kpi-val">
                            {toolkit.erosion_usle.mean_soil_loss_t_ha.toFixed(
                              2,
                            )}{' '}
                            t/ha
                          </strong>
                          <span className="kpi-sub">
                            Riesgo{' '}
                            {toolkit.erosion_usle.erosion_severity.toUpperCase()}
                          </span>
                        </div>
                        <div className="kpi-box kpi-amber">
                          <span className="kpi-label">Tierra perdida total</span>
                          <strong className="kpi-val">
                            {toolkit.erosion_usle.total_field_soil_loss_tons.toFixed(
                              1,
                            )}{' '}
                            t
                          </strong>
                          <span className="kpi-sub">
                            En todo el lote por esta tormenta
                          </span>
                        </div>
                      </div>
                      <p style={{ marginTop: 8 }}>
                        <strong>¿Dónde se pueden formar cárcavas/zanjas?</strong>{' '}
                        Se detectaron{' '}
                        <strong>
                          {toolkit.erosion_usle.gully_risk_area_ha.toFixed(2)}{' '}
                          ha
                        </strong>{' '}
                        ({toolkit.erosion_usle.gully_initiation_cells} sectores)
                        donde el agua toma demasiada fuerza. Mantené esos
                        sectores siempre empastados o con cultivo de servicio.
                      </p>
                    </div>
                  )}

                  {agroToolTab === 'terrazas' && (
                    <div className="agro-explain">
                      <h4>2. Curvas de nivel y Terrazas: ¿cuánto frenan?</h4>
                      <p>
                        Para la pendiente media de este lote (
                        <strong>
                          {toolkit.contour_terraces.mean_field_slope_pct.toFixed(
                            2,
                          )}{' '}
                          %
                        </strong>
                        ), el diseño recomendado por INTA es:
                      </p>
                      <ul className="agro-list">
                        <li>
                          <strong>Distancia entre terrazas:</strong> cada{' '}
                          <strong>
                            {
                              toolkit.contour_terraces
                                .recommended_horizontal_spacing_m
                            }{' '}
                            metros
                          </strong>{' '}
                          ({toolkit.contour_terraces.recommended_vertical_interval_m}{' '}
                          m de desnivel).
                        </li>
                        <li>
                          <strong>Agua que frenan las terrazas:</strong>{' '}
                          retienen{' '}
                          <strong>
                            {toolkit.contour_terraces.water_retained_by_terraces_m3.toFixed(
                              0,
                            )}{' '}
                            m³
                          </strong>{' '}
                          dentro del lote (bajan la escorrentía un{' '}
                          <strong>
                            {toolkit.contour_terraces.runoff_reduction_pct.toFixed(
                              0,
                            )}{' '}
                            %
                          </strong>
                          ).
                        </li>
                        <li>
                          <strong>Suelo que salvan de la erosión:</strong> la
                          pérdida baja de{' '}
                          {toolkit.contour_terraces.soil_loss_before_t_ha.toFixed(
                            2,
                          )}{' '}
                          a{' '}
                          <strong>
                            {toolkit.contour_terraces.soil_loss_after_t_ha.toFixed(
                              2,
                            )}{' '}
                            t/ha
                          </strong>{' '}
                          (ahorrás{' '}
                          <strong>
                            {toolkit.contour_terraces.erosion_reduction_pct.toFixed(
                              0,
                            )}{' '}
                            %
                          </strong>{' '}
                          de suelo).
                        </li>
                      </ul>
                    </div>
                  )}

                  {agroToolTab === 'balance' && (
                    <div className="agro-explain">
                      <h4>3. Balance hídrico del lote mes a mes (NASA POWER)</h4>
                      <p>
                        Lluvia anual:{' '}
                        <strong>
                          {toolkit.water_balance_monthly.annual_precipitation_mm.toFixed(
                            0,
                          )}{' '}
                          mm
                        </strong>{' '}
                        · Agua útil hoy en el suelo:{' '}
                        <strong>
                          {toolkit.water_balance_monthly.final_available_water_mm.toFixed(
                            0,
                          )}{' '}
                          mm (
                          {toolkit.water_balance_monthly.final_available_water_pct.toFixed(
                            0,
                          )}
                          %)
                        </strong>
                        .
                      </p>
                      <table className="mini-table">
                        <thead>
                          <tr>
                            <th>Mes</th>
                            <th>Lluvia</th>
                            <th>Consumo ET0</th>
                            <th>Agua Útil</th>
                            <th>Estado</th>
                          </tr>
                        </thead>
                        <tbody>
                          {toolkit.water_balance_monthly.months
                            .slice(-8)
                            .map((m) => (
                              <tr key={m.label}>
                                <td>{m.label}</td>
                                <td>{m.precipitation_mm.toFixed(0)} mm</td>
                                <td>{m.et0_mm.toFixed(0)} mm</td>
                                <td>{m.available_water_pct.toFixed(0)} %</td>
                                <td>
                                  <strong>{m.status}</strong>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {agroToolTab === 'anegamiento' && (
                    <div className="agro-explain">
                      <h4>4. Riesgo de anegamiento en tormentas reales</h4>
                      <p>
                        Analizando los días de lluvia reales de la zona (y cuánta
                        humedad había los 5 días previos a cada tormenta):
                      </p>
                      <table className="mini-table">
                        <thead>
                          <tr>
                            <th>Fecha real</th>
                            <th>Lluvia</th>
                            <th>Escurrió</th>
                            <th>Bajos aneg.</th>
                            <th>Riesgo</th>
                          </tr>
                        </thead>
                        <tbody>
                          {toolkit.real_waterlogging_by_date.top_historical_events
                            .slice(0, 6)
                            .map((ev) => (
                              <tr key={ev.date}>
                                <td>{ev.date}</td>
                                <td>{ev.precipitation_mm.toFixed(0)} mm</td>
                                <td>{ev.runoff_q_mm.toFixed(1)} mm</td>
                                <td>
                                  {ev.estimated_waterlogged_area_ha.toFixed(1)}{' '}
                                  ha
                                </td>
                                <td>
                                  <strong>
                                    {ev.waterlogging_risk.toUpperCase()}
                                  </strong>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {agroToolTab === 'siembra' && (
                    <div className="agro-explain">
                      <h4>5. Calculadora de Siembra y Fertilizante (INTA)</h4>
                      <div className="two-cols" style={{ marginBottom: 8 }}>
                        <select
                          value={
                            (toolkit.parameters.crop_code as string) ||
                            'maiz_temprano'
                          }
                          onChange={(e) =>
                            handleRunToolkit({
                              soil_group: quickSoilGroup,
                              cover_code: quickCover,
                              storm_precipitation_mm: quickRainMm,
                              crop_code: e.target.value,
                              environment_zone:
                                (toolkit.parameters.environment_zone as
                                  | 'loma'
                                  | 'media_loma'
                                  | 'bajo') || 'media_loma',
                            })
                          }
                        >
                          <option value="maiz_temprano">Maíz Temprano</option>
                          <option value="maiz_tardio">Maíz Tardío</option>
                          <option value="soja_primera">Soja de 1ª</option>
                          <option value="trigo">Trigo pan</option>
                          <option value="girasol">Girasol</option>
                          <option value="sorgo_granifero">
                            Sorgo Granífero
                          </option>
                          <option value="vicia_centeno_cobertura">
                            Vicia + Centeno
                          </option>
                        </select>
                        <select
                          value={
                            (toolkit.parameters.environment_zone as string) ||
                            'media_loma'
                          }
                          onChange={(e) =>
                            handleRunToolkit({
                              soil_group: quickSoilGroup,
                              cover_code: quickCover,
                              storm_precipitation_mm: quickRainMm,
                              crop_code:
                                (toolkit.parameters.crop_code as string) ||
                                'maiz_temprano',
                              environment_zone: e.target.value as
                                | 'loma'
                                | 'media_loma'
                                | 'bajo',
                            })
                          }
                        >
                          <option value="loma">Ambiente: Loma</option>
                          <option value="media_loma">
                            Ambiente: Media Loma
                          </option>
                          <option value="bajo">Ambiente: Bajo</option>
                        </select>
                      </div>
                      <ul className="agro-list">
                        <li>
                          <strong>Densidad a lograr:</strong>{' '}
                          {toolkit.seeding_calculator_inta.target_plants_ha.toLocaleString()}{' '}
                          plantas/ha (calibrar sembradora a{' '}
                          <strong>
                            {toolkit.seeding_calculator_inta.seeds_per_linear_m.toFixed(
                              1,
                            )}{' '}
                            semillas/metro
                          </strong>
                          ).
                        </li>
                        <li>
                          <strong>Compra de semilla:</strong>{' '}
                          <strong>
                            {toolkit.seeding_calculator_inta.seed_density_kg_ha.toFixed(
                              1,
                            )}{' '}
                            kg/ha
                          </strong>{' '}
                          →{' '}
                          <strong>
                            {toolkit.seeding_calculator_inta.commercial_bags_needed.toFixed(
                              1,
                            )}{' '}
                            bolsas
                          </strong>{' '}
                          ({toolkit.seeding_calculator_inta.bag_unit}) para todo
                          el lote.
                        </li>
                        <li>
                          <strong>Fertilización guía (rinde objetivo{' '}
                          {toolkit.seeding_calculator_inta.target_yield_t_ha}{' '}
                          t/ha):</strong>{' '}
                          <strong>
                            MAP{' '}
                            {toolkit.seeding_calculator_inta.commercial_fertilizer_guide_kg_ha.MAP_11_52_0_kg_ha.toFixed(
                              0,
                            )}{' '}
                            kg/ha
                          </strong>{' '}
                          +{' '}
                          <strong>
                            Urea{' '}
                            {toolkit.seeding_calculator_inta.commercial_fertilizer_guide_kg_ha.Urea_46_0_0_kg_ha.toFixed(
                              0,
                            )}{' '}
                            kg/ha
                          </strong>{' '}
                          +{' '}
                          <strong>
                            Yeso{' '}
                            {toolkit.seeding_calculator_inta.commercial_fertilizer_guide_kg_ha.Yeso_agricola_17S_kg_ha.toFixed(
                              0,
                            )}{' '}
                            kg/ha
                          </strong>
                          .
                        </li>
                      </ul>
                    </div>
                  )}

                  {agroToolTab === 'rotaciones' && (
                    <div className="agro-explain">
                      <h4>6. Comparador de Rotaciones (3 años lado a lado)</h4>
                      <p>
                        ¿Qué pasa en este lote si hacés{' '}
                        <strong>Monocultivo / Baja cobertura (A)</strong> vs.{' '}
                        <strong>
                          Rotación Sustentable RotaTerra con Cultivo de Servicio
                          (B)
                        </strong>
                        ?
                      </p>
                      <div className="kpi-cards">
                        <div className="kpi-box kpi-green">
                          <span className="kpi-label">Tierra que salvás</span>
                          <strong className="kpi-val">
                            {toolkit.rotation_comparator_3yr.delta_b_vs_a.soil_saved_by_b_tons.toFixed(
                              1,
                            )}{' '}
                            t
                          </strong>
                          <span className="kpi-sub">
                            Menos erosión en 3 campañas
                          </span>
                        </div>
                        <div className="kpi-box kpi-blue">
                          <span className="kpi-label">Agua extra retenida</span>
                          <strong className="kpi-val">
                            +
                            {toolkit.rotation_comparator_3yr.delta_b_vs_a.runoff_saved_by_b_mm.toFixed(
                              0,
                            )}{' '}
                            mm
                          </strong>
                          <span className="kpi-sub">
                            Que infiltra en vez de perderse
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {agroToolTab === 'ndvi' && (
                    <div className="agro-explain">
                      <h4>7. Monitor de Vigor Vegetativo (NDVI)</h4>
                      <p>
                        NDVI medio del lote:{' '}
                        <strong>
                          {toolkit.ndvi_vigor_monitor.mean_ndvi_in_field.toFixed(
                            2,
                          )}
                        </strong>
                        . Se detectan{' '}
                        <strong>
                          {toolkit.ndvi_vigor_monitor.low_vigor_area_ha.toFixed(
                            1,
                          )}{' '}
                          ha ({toolkit.ndvi_vigor_monitor.low_vigor_pct.toFixed(1)}{' '}
                          %)
                        </strong>{' '}
                        con menor vigor vegetativo.
                      </p>
                      <p>
                        <strong>Cruza con el relieve 3D:</strong> el{' '}
                        <strong>
                          {toolkit.ndvi_vigor_monitor.weak_zones_explained_by_waterlogging_or_erosion_pct.toFixed(
                            0,
                          )}{' '}
                          %
                        </strong>{' '}
                        de las zonas débiles del cultivo coincide directamente
                        con los bajos anegables o las vías de escurrimiento.
                      </p>
                    </div>
                  )}

                  {agroToolTab === 'heladas' && (
                    <div className="agro-explain">
                      <h4>8. Riesgo de Heladas y Fechas Seguras de Siembra</h4>
                      <ul className="agro-list">
                        <li>
                          <strong>Última helada tardía (primavera):</strong>{' '}
                          mediana el{' '}
                          <strong>
                            {
                              toolkit.frost_risk_sowing
                                .median_last_spring_frost_date
                            }
                          </strong>{' '}
                          · Fecha segura (riesgo &lt;10%): desde el{' '}
                          <strong>
                            {
                              toolkit.frost_risk_sowing
                                .safe_spring_sowing_start_date
                            }
                          </strong>
                          .
                        </li>
                        <li>
                          <strong>Primera helada temprana (otoño):</strong>{' '}
                          <strong>
                            {
                              toolkit.frost_risk_sowing
                                .median_first_autumn_frost_date
                            }
                          </strong>{' '}
                          ({toolkit.frost_risk_sowing.frost_free_period_days}{' '}
                          días libres de heladas).
                        </li>
                        {toolkit.frost_risk_sowing.safe_sowing_windows_by_crop.map(
                          (w) => (
                            <li key={w.crop}>
                              <strong>{w.crop}</strong> (sembrar desde{' '}
                              {w.safe_start}): {w.note}
                            </li>
                          ),
                        )}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </section>
          </aside>
        </div>
      ) : (
        /* Modo Técnico GIS Regional completo (MapLibre + Todos los parámetros avanzados) */
        <div className="workspace">
          <aside className="sidebar sidebar-left">
            <section className="card">
              <div className="card-header">
                <h3>1. Lotes agrícolas</h3>
              </div>
              <div className="btn-row">
                <button
                  className="btn-primary"
                  onClick={() => handleQuickLoadAndSimulateField('serrano')}
                  disabled={Boolean(busy)}
                >
                  Lote Serrano #492
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => handleQuickLoadAndSimulateField('llanura')}
                  disabled={Boolean(busy)}
                >
                  Lote Llanura #205
                </button>
              </div>
              <label className="btn-secondary full-width">
                Importar Lote (GeoJSON/KML/SHP)
                <input
                  type="file"
                  accept=".geojson,.json,.kml,.kmz,.zip"
                  onChange={handleImportGeoJSON}
                  hidden
                />
              </label>

              {fields.length > 0 && (
                <label className="field-label" style={{ marginTop: 8 }}>
                  Lote activo
                  <select
                    value={activeFieldId ?? ''}
                    onChange={(e) => setActiveFieldId(e.target.value)}
                  >
                    {fields.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name} ({f.area_ha.toFixed(1)} ha)
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </section>

            <section className="card">
              <h3>2. Modelo Digital de Elevación (MDE)</h3>
              <label className="field-label">
                Fuente de elevación
                <select
                  value={sourceId}
                  onChange={(e) =>
                    setSourceId(
                      e.target.value as 'copernicus_glo30' | 'upload',
                    )
                  }
                >
                  <option value="copernicus_glo30">
                    Copernicus DEM GLO-30 (30 m · ESA / AWS COG)
                  </option>
                  <option value="upload">
                    Subir GeoTIFF propio (Dron / LiDAR / IGN 5 m)
                  </option>
                </select>
              </label>
              <label className="field-label">
                Zona de aporte externa (buffer en metros)
                <input
                  type="number"
                  min={0}
                  max={5000}
                  step={50}
                  value={bufferM}
                  onChange={(e) => setBufferM(Number(e.target.value))}
                />
              </label>
              {sourceId === 'upload' && (
                <div className="upload-meta">
                  <label className="field-label">
                    Archivo GeoTIFF
                    <input
                      type="file"
                      accept=".tif,.tiff,image/tiff"
                      onChange={(e) =>
                        setUploadFile(e.target.files?.[0] ?? null)
                      }
                    />
                  </label>
                  <label className="field-label">
                    Tipo de superficie
                    <select
                      value={uploadSurfaceType}
                      onChange={(e) =>
                        setUploadSurfaceType(
                          e.target.value as 'DTM' | 'DSM' | 'desconocido',
                        )
                      }
                    >
                      <option value="DTM">MDT / DTM (terreno desnudo)</option>
                      <option value="DSM">MDS / DSM (superficie)</option>
                      <option value="desconocido">No declarado</option>
                    </select>
                  </label>
                  <div className="two-cols">
                    <label className="field-label">
                      Datum vertical
                      <input
                        type="text"
                        value={uploadDatum}
                        onChange={(e) => setUploadDatum(e.target.value)}
                      />
                    </label>
                    <label className="field-label">
                      Precisión ± (m)
                      <input
                        type="number"
                        step="0.05"
                        value={uploadAccuracy}
                        onChange={(e) => setUploadAccuracy(e.target.value)}
                      />
                    </label>
                  </div>
                </div>
              )}
              <button
                className="btn-primary full-width"
                onClick={handleProcessTerrain}
                disabled={!activeField || Boolean(busy)}
              >
                {terrain ? 'Reprocesar DEM del lote' : 'Cargar y procesar DEM'}
              </button>
            </section>

            <HydrologyPanel
              hasTerrain={Boolean(terrain)}
              hydrology={hydrology}
              busy={Boolean(busy)}
              onRun={handleRunHydrology}
            />

            <RainfallRunoffPanel
              hasTerrain={Boolean(terrain)}
              events={rainfallEvents}
              runs={runoffRuns}
              comparison={comparison}
              busy={Boolean(busy)}
              onCreateManualEvent={handleCreateManualEvent}
              onLoadSampleEvent={handleLoadSampleEvent}
              onImportCsvEvent={handleImportCsvEvent}
              onRunRunoff={handleRunRunoff}
              onActivateRun={handleActivateRunoff}
              onRun2DSolver={handleRun2DSolver}
              onCompare={handleCompareScenarios}
            />

            <section className="card">
              <h3>7. Capas del visor GIS 2D / 3D</h3>
              <div
                className="segmented"
                style={{ marginBottom: 8, width: '100%' }}
              >
                <button
                  style={{ flex: 1 }}
                  className={viewMode === '2d' ? 'active' : ''}
                  onClick={() => setViewMode('2d')}
                >
                  Mapa 2D
                </button>
                <button
                  style={{ flex: 1 }}
                  className={viewMode === '3d' ? 'active' : ''}
                  onClick={() => setViewMode('3d')}
                >
                  Mapa 3D
                </button>
              </div>
              <div
                className="segmented"
                style={{ marginBottom: 8, width: '100%' }}
              >
                <button
                  style={{ flex: 1 }}
                  className={interactionMode === 'inspect' ? 'active' : ''}
                  onClick={() => setInteractionMode('inspect')}
                >
                  Inspeccionar
                </button>
                <button
                  style={{ flex: 1 }}
                  className={interactionMode === 'profile' ? 'active' : ''}
                  onClick={() => setInteractionMode('profile')}
                >
                  Perfil ({profileDraft.length})
                </button>
                <button
                  style={{ flex: 1 }}
                  className={interactionMode === 'observe' ? 'active' : ''}
                  onClick={() => setInteractionMode('observe')}
                >
                  + Obs ({observations.length})
                </button>
              </div>
              <label className="field-label">
                Variable en superficie 3D
                <select
                  value={layers.surfaceColor}
                  onChange={(e) =>
                    setLayers({
                      ...layers,
                      surfaceColor: e.target.value as SurfaceColorMode,
                    })
                  }
                >
                  <option value="elevation">
                    Elevación (gradiente hipsométrico)
                  </option>
                  <option value="hillshade">
                    Sombreado de relieve (Hillshade)
                  </option>
                  <option value="slope">Pendiente local (%)</option>
                  <option value="mfd" disabled={!hydrology}>
                    Acumulación de flujo difuso MFD (ha)
                  </option>
                  <option value="d8" disabled={!hydrology}>
                    Acumulación de flujo concentrado D8 (ha)
                  </option>
                  <option value="depressions" disabled={!hydrology}>
                    Profundidad de depresiones / bajos (m)
                  </option>
                  <option value="subbasins" disabled={!hydrology}>
                    Subcuencas por punto de salida
                  </option>
                  <option value="twi" disabled={!hydrology}>
                    Índice Humedad Topográfica (TWI)
                  </option>
                  <option value="spi" disabled={!hydrology}>
                    Índice Potencia Erosiva (SPI)
                  </option>
                  <option value="agronomic_zones" disabled={!hydrology}>
                    Ambientes Hidro-Agronómicos RotaTerra
                  </option>
                  <option value="runoff" disabled={runoffRuns.length === 0}>
                    Escorrentía estimada NRCS-CN + MFD
                  </option>
                  <option value="water_depth" disabled={!mesh?.water_depth_m}>
                    Profundidad de agua 2D Manning (m)
                  </option>
                  <option value="velocity" disabled={!mesh?.velocity_m_s}>
                    Velocidad superficial 2D Manning (m/s)
                  </option>
                  <option value="erosion" disabled={!mesh?.soil_loss_t_ha}>
                    Pérdida de suelo por tormenta USLE (t/ha)
                  </option>
                  <option value="ndvi" disabled={!mesh?.ndvi}>
                    Monitor de Vigor Vegetativo (NDVI)
                  </option>
                </select>
              </label>
            </section>
          </aside>

          <main className="center-stage">
            {busy && <div className="status-toast">{busy}</div>}
            {error && (
              <div className="error-toast" role="alert">
                <span>{error}</span>
                <button onClick={() => setError(null)}>✕</button>
              </div>
            )}
            <TerrainScene3D
              field={activeField}
              mesh={mesh}
              hydrology={hydrology}
              observations={observations}
              particlePaths={timeline?.particle_paths ?? []}
              showParticles={showParticles}
              transitFraction={
                timeline?.has_time_series && timeline.frames[timelineStep]
                  ? timeline.frames[timelineStep].transit_fraction_of_peak
                  : 1.0
              }
              viewMode={viewMode}
              exaggeration={exaggeration}
              layers={layers}
              interactionMode={interactionMode}
              profileDraft={profileDraft}
              selectedPoint={selectedPoint}
              onMapClick={handleMapClick}
              onCursorMove={(lon, lat) => setCursorCoords([lon, lat])}
            />
          </main>

          <aside className="sidebar sidebar-right">
            <AgronomicToolkitPanel
              hasTerrain={Boolean(terrain)}
              toolkit={toolkit}
              busy={Boolean(busy)}
              onRun={handleRunToolkit}
              onSelect3DLayer={(layer) =>
                setLayers((prev) => ({ ...prev, surfaceColor: layer }))
              }
            />

            {timeline && (
              <FlowTimelinePlayer
                timeline={timeline}
                currentStep={timelineStep}
                playing={playing}
                speed={playSpeed}
                showParticles={showParticles}
                onStepChange={(s) => setTimelineStep(s)}
                onTogglePlay={() => setPlaying((p) => !p)}
                onReset={() => {
                  setPlaying(false)
                  setTimelineStep(0)
                }}
                onSpeedChange={(sp) => setPlaySpeed(sp)}
                onToggleParticles={(sh) => setShowParticles(sh)}
              />
            )}

            {profileResult && (
              <ProfileChart
                profile={profileResult}
                onClear={() => {
                  setProfileDraft([])
                  setProfileResult(null)
                }}
              />
            )}

            {activeField && (
              <QualityPanel
                field={activeField}
                terrain={terrain}
                mesh={mesh}
              />
            )}
          </aside>
        </div>
      )}

      <footer className="bottombar">
        <span>
          Lote: <strong>{activeField?.name ?? '—'}</strong> (
          {activeField ? `${activeField.area_ha.toFixed(1)} ha` : '—'})
        </span>
        <span>
          Fuente relieve:{' '}
          {terrain
            ? `${terrain.source.source_name} (${terrain.quality.pixel_size_m.toFixed(0)} m)`
            : '—'}
        </span>
        <span>
          Lluvia activa: <strong>{quickRainMm} mm</strong>
        </span>
        <span className="phase-note">
          RotaTerra · Simulación agro-hidrológica trazable (Copernicus + NASA
          POWER + INTA + Sentinel-2)
        </span>
      </footer>

      <PolygonMapDrawer
        isOpen={isMapDrawerOpen}
        initialCenter={activeField?.centroid ?? [-66.085, -33.128]}
        onClose={() => setIsMapDrawerOpen(false)}
        onConfirmPolygon={async (name, file) => {
          await handleFullImportAndSimulate(file, name)
        }}
      />
    </div>
  )
}
