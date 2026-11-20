import { useEffect, useState } from 'react'

interface Props {
  message: string | null
  onDismiss?: () => void
  fieldName?: string | null
  fieldAreaHa?: number | null
}

const AGRO_TIPS = [
  {
    icon: '🌾',
    title: 'Siembra Directa y Conservación',
    text: 'Mantener más del 30% del suelo cubierto con rastrojo reduce la velocidad de la escorrentía superficial hasta un 70% y previene la formación de cárcavas.',
  },
  {
    icon: '🛰️',
    title: 'Radar SAR y Humedad de Suelo',
    text: 'Los radares SAR en Banda L (como SAOCOM) estiman la humedad del suelo y rugosidad superficial; no son pluviómetros ni miden lluvia directa.',
  },
  {
    icon: '🌧️',
    title: 'Red de Estaciones SMN',
    text: 'Las estaciones del Servicio Meteorológico Nacional se utilizan como referencia geográfica de proximidad al establecimiento.',
  },
  {
    icon: '🌱',
    title: 'Humedad Antecedente (AMC)',
    text: 'Un suelo con lluvias en los 5 días previos (AMC III) tiene menor capacidad de infiltración, provocando mayor escurrimiento hacia los bajos.',
  },
  {
    icon: '⛰️',
    title: 'Terrazas y Curvas de Nivel',
    text: 'Sistematizar el lote con terrazas a nivel frena el agua en las lomas y retiene humedad valiosa para el cultivo durante los meses de verano.',
  },
  {
    icon: '🌽',
    title: 'Agua Útil en el Perfil',
    text: 'Por cada milímetro de agua útil almacenada en los primeros 100 cm de suelo, el maíz puede rendir entre 18 y 22 kg adicionales de grano por hectárea.',
  },
]

export function AgroLoadingOverlay({
  message,
  onDismiss,
  fieldName,
  fieldAreaHa,
}: Props) {
  const [tipIndex, setTipIndex] = useState<number>(0)
  const [tipFade, setTipFade] = useState<boolean>(true)

  // Rotar consejos agronómicos cada 4.2 segundos con suave transición de desvanecimiento
  useEffect(() => {
    if (!message) return
    const interval = window.setInterval(() => {
      setTipFade(false)
      window.setTimeout(() => {
        setTipIndex((prev) => (prev + 1) % AGRO_TIPS.length)
        setTipFade(true)
      }, 250)
    }, 4200)
    return () => window.clearInterval(interval)
  }, [message])

  if (!message) return null

  const currentTip = AGRO_TIPS[tipIndex]

  return (
    <div className="agro-loading-overlay" role="dialog" aria-modal="true">
      <div className="agro-loading-card">
        {/* Cabecera con branding agronómico */}
        <div className="agro-loading-header">
          <div className="agro-brand-tag">
            <span className="agro-leaf">🌾</span>
            <span>RotaTerra Agro-Hidrológico</span>
          </div>
          {onDismiss && (
            <button
              type="button"
              className="agro-dismiss-btn"
              onClick={onDismiss}
              title="Continuar en segundo plano"
            >
              ✕
            </button>
          )}
        </div>

        {/* Ilustración Animada Agrícola y Satelital */}
        <div className="agro-illustration-container">
          <svg
            className="agro-svg-art"
            viewBox="0 0 320 180"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Cielo y resplandor al amanecer */}
            <circle cx="160" cy="180" r="140" fill="url(#sunGlow)" opacity="0.25" />

            {/* Satélite orbitando y emitiendo ondas de radar hacia el campo */}
            <g className="agro-satellite-group">
              <path
                d="M 230 40 L 250 40 M 240 32 L 240 48"
                stroke="#38bdf8"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <rect
                x="235"
                y="36"
                width="10"
                height="8"
                rx="2"
                fill="#0284c7"
                stroke="#7dd3fc"
                strokeWidth="1.5"
              />
              {/* Paneles solares */}
              <rect x="222" y="37" width="10" height="6" rx="1" fill="#0369a1" />
              <rect x="248" y="37" width="10" height="6" rx="1" fill="#0369a1" />
              {/* Haz de radar hacia la tierra */}
              <path
                d="M 240 48 L 190 145 M 240 48 L 260 145"
                stroke="#38bdf8"
                strokeWidth="1.2"
                strokeDasharray="4 4"
                className="radar-scan-line"
                opacity="0.6"
              />
            </g>

            {/* Relieve topográfico: Loma y bajo en perspectiva */}
            <path
              d="M 0 150 Q 80 120 160 142 T 320 135 L 320 180 L 0 180 Z"
              fill="url(#soilGradient)"
            />
            {/* Surcos de siembra directa en contorno */}
            <path
              d="M 10 156 Q 85 128 160 148 T 310 142"
              stroke="#047857"
              strokeWidth="2.5"
              strokeDasharray="6 5"
              opacity="0.75"
            />
            <path
              d="M 5 166 Q 85 138 160 158 T 315 152"
              stroke="#065f46"
              strokeWidth="3"
              strokeDasharray="8 6"
              opacity="0.85"
            />

            {/* Brote central de cultivo meciéndose con el viento */}
            <g className="agro-sprout-group">
              {/* Tallo */}
              <path
                d="M 160 144 Q 158 126 160 110"
                stroke="#10b981"
                strokeWidth="3.5"
                strokeLinecap="round"
              />
              {/* Hoja izquierda */}
              <path
                d="M 160 126 C 145 122 135 110 140 102 C 148 102 156 114 160 124"
                fill="#34d399"
                stroke="#059669"
                strokeWidth="1"
              />
              {/* Hoja derecha superior */}
              <path
                d="M 160 118 C 175 114 185 102 180 94 C 172 94 164 106 160 116"
                fill="#10b981"
                stroke="#047857"
                strokeWidth="1"
              />
              {/* Brote apical */}
              <circle cx="160" cy="108" r="3" fill="#6ee7b7" />
            </g>

            {/* Gotas de lluvia cayendo desde las nubes */}
            <g className="agro-rain-drops">
              <line
                x1="90"
                y1="50"
                x2="85"
                y2="70"
                stroke="#38bdf8"
                strokeWidth="2"
                strokeLinecap="round"
                className="rain-drop-anim drop-1"
              />
              <line
                x1="130"
                y1="40"
                x2="125"
                y2="60"
                stroke="#38bdf8"
                strokeWidth="2"
                strokeLinecap="round"
                className="rain-drop-anim drop-2"
              />
              <line
                x1="180"
                y1="45"
                x2="175"
                y2="65"
                stroke="#38bdf8"
                strokeWidth="2"
                strokeLinecap="round"
                className="rain-drop-anim drop-3"
              />
            </g>

            {/* Ondas concéntricas de infiltración en el suelo */}
            <ellipse
              cx="160"
              cy="162"
              rx="24"
              ry="7"
              stroke="#38bdf8"
              strokeWidth="1.5"
              fill="none"
              className="soil-ripple-anim"
            />
            <ellipse
              cx="160"
              cy="162"
              rx="40"
              ry="11"
              stroke="#0284c7"
              strokeWidth="1.2"
              fill="none"
              className="soil-ripple-anim-2"
            />

            <defs>
              <radialGradient id="sunGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#0f172a" stopOpacity="0" />
              </radialGradient>
              <linearGradient id="soilGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#064e3b" />
                <stop offset="50%" stopColor="#022c22" />
                <stop offset="100%" stopColor="#0f172a" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* Mensaje de la tarea en curso */}
        <div className="agro-loading-body">
          <h3 className="agro-loading-title">{message}</h3>
          {fieldName && (
            <p className="agro-field-sub">
              Lote: <strong>{fieldName}</strong>
              {fieldAreaHa ? ` · ${fieldAreaHa.toFixed(1)} ha` : ''}
            </p>
          )}

          {/* Barra de progreso fluida agronómica */}
          <div className="agro-progress-track">
            <div className="agro-progress-bar" />
          </div>

          {/* Pasos del motor de cálculo */}
          <div className="agro-steps-row">
            <span className="agro-step-badge active">
              🛰️ 1. Relieve Satelital
            </span>
            <span className="agro-step-arrow">→</span>
            <span className="agro-step-badge active">
              💧 2. Drenaje y Bajos
            </span>
            <span className="agro-step-arrow">→</span>
            <span className="agro-step-badge active">
              🌧️ 3. Serie Climática
            </span>
            <span className="agro-step-arrow">→</span>
            <span className="agro-step-badge active">
              🧊 4. Maqueta 3D
            </span>
          </div>

          {/* Tarjeta de Conocimiento Agronómico Rotativo */}
          <div
            className={`agro-tip-box ${tipFade ? 'fade-in' : 'fade-out'}`}
          >
            <div className="agro-tip-header">
              <span className="agro-tip-icon">{currentTip.icon}</span>
              <strong>{currentTip.title}</strong>
            </div>
            <p className="agro-tip-text">{currentTip.text}</p>
          </div>
        </div>

        {/* Pie con acción secundaria */}
        {onDismiss && (
          <div className="agro-loading-footer">
            <button
              type="button"
              className="btn-secondary agro-footer-btn"
              onClick={onDismiss}
            >
              Continuar explorando en segundo plano
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
