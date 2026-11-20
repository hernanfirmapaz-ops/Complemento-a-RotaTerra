import { useState } from 'react'
import {
  Button,
  Segmented,
  OptionList,
  Metric,
  Details,
  Legend,
  SourceNote,
  Icon,
  ProgressBar,
  BottomSheet,
  type OptionListItem,
  type IconName,
} from './index'

export function ComponentShowcase({ onClose }: { onClose?: () => void }) {
  const [segmentedVal, setSegmentedVal] = useState<'lote' | 'lluvia' | 'resultado'>('lote')
  const [selectedOption, setSelectedOption] = useState<string>('opt1')
  const [isSimulatingWork, setIsSimulatingWork] = useState<boolean>(false)
  const [workMessage, setWorkMessage] = useState<string | null>(null)
  const [showMobileSheet, setShowMobileSheet] = useState<boolean>(false)

  const handleStartWork = () => {
    setIsSimulatingWork(true)
    setWorkMessage('Descargando relieve satelital Copernicus GLO-30 (30 m)...')
    setTimeout(() => {
      setWorkMessage('Calculando red de drenaje y bajos de retención...')
    }, 1800)
    setTimeout(() => {
      setWorkMessage('Consultando estación SMN y balance hídrico NASA POWER...')
    }, 3600)
    setTimeout(() => {
      setIsSimulatingWork(false)
      setWorkMessage(null)
    }, 5400)
  }

  const sampleOptions: OptionListItem[] = [
    {
      id: 'opt1',
      title: 'Lote Norte San Luis',
      subtitle: '223,4 ha · Pendiente media 2,8%',
      meta: '223 ha',
      icon: 'map-pin',
      badge: 'Catastro',
    },
    {
      id: 'opt2',
      title: 'Potrero La Esperanza',
      subtitle: '148,2 ha · Suelo Argiudol típico',
      meta: '148 ha',
      icon: 'map-pin',
    },
    {
      id: 'opt3',
      title: 'Bajo de Retención Sur',
      subtitle: '78,0 ha · Riesgo de anegamiento',
      meta: '78 ha',
      icon: 'droplet',
      badge: 'Riesgo',
    },
  ]

  const sampleIcons: IconName[] = [
    'chevron-down',
    'chevron-right',
    'chevron-up',
    'arrow-right',
    'check',
    'alert-circle',
    'layers',
    'droplet',
    'sun',
    'compass',
    'maximize',
    'download',
    'info',
    'x',
    'map-pin',
    'upload',
    'refresh',
  ]

  return (
    <div className="showcase-page">
      {/* Barra de progreso interactiva activa */}
      <ProgressBar active={isSimulatingWork} message={workMessage} fixedTop />

      <header className="showcase-header">
        <div>
          <span className="showcase-tag">SDD-002 · TAREA 1.1</span>
          <h1>Sistema de Diseño Minimalista · Galería de Componentes</h1>
          <p className="showcase-sub">
            Componentes desacoplados, tokens CSS nativos, accesibles y libres de emojis según la especificación SDD-002.
          </p>
        </div>
        {onClose && (
          <Button variant="secondary" onClick={onClose} icon="x">
            Volver al Visor
          </Button>
        )}
      </header>

      <div className="showcase-grid">
        {/* Sección: Barra de carga y progreso */}
        <section className="showcase-card">
          <h2>1. Indicador de Carga y Progreso (ProgressBar)</h2>
          <p className="showcase-desc">
            Barra lineal fina con avance suave y chip con porcentaje. Reemplaza el bloqueo invasivo mientras se trabaja.
          </p>
          <div className="showcase-demo-col">
            <Button
              variant="primary"
              onClick={handleStartWork}
              loading={isSimulatingWork}
            >
              {isSimulatingWork ? 'Simulando trabajo...' : 'Probar Barra de Carga (5,4 s)'}
            </Button>
            <ProgressBar active={true} progress={42} message="Progreso explícito fijo al 42%" />
            <ProgressBar active={true} progress={85} message="Procesando terrazas y líneas de siembra..." />
          </div>
        </section>

        {/* Sección: Botones */}
        <section className="showcase-card">
          <h2>2. Botones (Button)</h2>
          <p className="showcase-desc">
            Un solo botón primario por vista. Botón secundario con borde sutil y botón de texto con flecha interactiva.
          </p>
          <div className="showcase-demo-row">
            <Button variant="primary">Continuar a Lluvia</Button>
            <Button variant="secondary">Descargar Informe</Button>
            <Button variant="text">Ver metodología</Button>
            <Button variant="danger">Descartar Lote</Button>
          </div>
          <div className="showcase-demo-row" style={{ marginTop: 12 }}>
            <Button variant="secondary" icon="upload">Importar KML/SHP</Button>
            <Button variant="secondary" icon="layers">Capas 3D</Button>
            <Button variant="primary" loading>Guardando</Button>
            <Button variant="secondary" disabled>Deshabilitado</Button>
          </div>
        </section>

        {/* Sección: Control Segmentado */}
        <section className="showcase-card">
          <h2>3. Control Segmentado (Segmented)</h2>
          <p className="showcase-desc">
            Fondo superficie, pestaña activa en blanco con relieve sutil de 1 px. Máximo 4 pasos.
          </p>
          <Segmented
            value={segmentedVal}
            onChange={(v) => setSegmentedVal(v as any)}
            options={[
              { value: 'lote', label: '1. Lote', sublabel: '223 ha' },
              { value: 'lluvia', label: '2. Lluvia', sublabel: '80 mm' },
              { value: 'resultado', label: '3. Resultado', sublabel: '3 ambientes' },
            ]}
          />
        </section>

        {/* Sección: Lista de Opciones */}
        <section className="showcase-card">
          <h2>4. Lista de Opciones (OptionList)</h2>
          <p className="showcase-desc">
            Filas de 56 px con divisor de 1 px, subtítulos discretos y chevron de navegación.
          </p>
          <OptionList
            items={sampleOptions}
            selectedId={selectedOption}
            onSelect={(item) => setSelectedOption(item.id)}
          />
        </section>

        {/* Sección: Métricas */}
        <section className="showcase-card">
          <h2>5. Métricas y Cifras Clave (Metric)</h2>
          <p className="showcase-desc">
            Cifras tabulares destacadas con unidades y rangos explícitos para no inventar certeza.
          </p>
          <div className="showcase-demo-row">
            <Metric
              value="18,4"
              unit="ha"
              range="16 – 21 ha"
              label="Superficie anegable estimada"
              caption="Para lluvia de 80 mm en 24 h"
            />
            <Metric
              value="2,8"
              unit="%"
              label="Pendiente media general"
              caption="Llanura ondulada típica"
            />
            <Metric
              value="80"
              unit="mm"
              label="Precipitación de diseño"
              caption="Estación SMN San Luis Aero"
            />
          </div>
        </section>

        {/* Sección: Detalles Técnicos */}
        <section className="showcase-card">
          <h2>6. Detalles Técnicos Plegables (Details)</h2>
          <p className="showcase-desc">
            Componente disclosure nativo. Mantiene limpia la primera pantalla ocultando la jerga técnica.
          </p>
          <Details
            summary="Ver parámetros del modelo hidrológico"
            subsummary="Curva Número (CN) y MFD"
          >
            <p style={{ margin: '8px 0', fontSize: 13, lineHeight: 1.5 }}>
              Método USDA-NRCS / SCS Curve Number adaptado a Siembra Directa continua en Argentina. Coeficiente de abstracción inicial λ = 0,20. Enrutamiento multidireccional Freeman MFD con exponente 1,1.
            </p>
          </Details>
        </section>

        {/* Sección: Leyendas de Datos */}
        <section className="showcase-card">
          <h2>7. Leyendas Cartográficas (Legend)</h2>
          <p className="showcase-desc">
            Barras de 120 × 6 px con escalas secuenciales accesibles para daltonismo.
          </p>
          <div className="showcase-demo-row" style={{ flexWrap: 'wrap', gap: 16 }}>
            <Legend
              type="water"
              title="Lámina de agua"
              minLabel="0 cm"
              maxLabel="85 cm"
            />
            <Legend
              type="relief"
              title="Cota topográfica"
              minLabel="680 m"
              maxLabel="742 m"
            />
            <Legend
              type="erosion"
              title="Riesgo de erosión"
              minLabel="Bajo"
              maxLabel="Severo"
            />
            <Legend
              type="ndvi"
              title="Vigor vegetal (NDVI)"
              minLabel="0,15"
              maxLabel="0,88"
            />
          </div>
        </section>

        {/* Sección: Fuentes y Avisos */}
        <section className="showcase-card">
          <h2>8. Notas de Fuentes y Avisos (SourceNote)</h2>
          <p className="showcase-desc">
            Atribución real y visible sin adornos. Avisos de 1 px a la izquierda.
          </p>
          <SourceNote
            source="Copernicus GLO-30"
            details="Resolución 30 m · Precisión vertical ±2 m"
            disclaimer="Agencia Espacial Europea (ESA)"
          />
          <SourceNote
            source="NASA POWER"
            details="Cuadrícula 0.5° (~55 km) · Referencia SMN San Luis Aero (OMM 87436 a 22 km)"
          />
          <SourceNote
            isNotice
            source=""
            disclaimer="Aviso de campo: los resultados son estimaciones hidrológicas para planificación agrícola y no sustituyen el relevamiento altimétrico con estación total o RTK."
          />
        </section>

        {/* Sección: Íconos */}
        <section className="showcase-card showcase-card-full">
          <h2>9. Colección de Íconos SVG Minimalistas (0 emojis)</h2>
          <p className="showcase-desc">
            Trazo limpio de 1,5 px, 20 px, estilo Lucide/SF Symbols, mono-color adaptativo.
          </p>
          <div className="showcase-icons-grid">
            {sampleIcons.map((ic) => (
              <div key={ic} className="showcase-icon-item">
                <Icon name={ic} size={22} />
                <span>{ic}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Botón para previsualizar BottomSheet en móvil */}
      <div style={{ textAlign: 'center', marginTop: 24, marginBottom: 40 }}>
        <Button
          variant="secondary"
          onClick={() => setShowMobileSheet(!showMobileSheet)}
          icon="layers"
        >
          {showMobileSheet ? 'Ocultar Hoja Inferior' : 'Previsualizar Hoja Inferior Móvil'}
        </Button>
      </div>

      {showMobileSheet && (
        <BottomSheet
          headerTitle="Lote Seleccionado (Móvil)"
          headerAction={
            <Button variant="text" onClick={() => setShowMobileSheet(false)}>
              Cerrar
            </Button>
          }
        >
          <p style={{ margin: 0, fontSize: 14, color: 'var(--ink-2)' }}>
            Contenido de la hoja inferior en 3 alturas (plegada a 72 px, media a 50% y completa a 90%).
          </p>
        </BottomSheet>
      )}
    </div>
  )
}
