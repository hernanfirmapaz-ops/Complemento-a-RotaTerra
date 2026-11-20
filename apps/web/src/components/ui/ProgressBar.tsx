import { useEffect, useState } from 'react'

interface ProgressBarProps {
  active: boolean
  message?: string | null
  /** Si se omite, se ejecuta una animación fluida indeterminada con avance suave simulado. */
  progress?: number
  /** Si es true, renderiza la barra lineal fija en la parte superior de la pantalla. */
  fixedTop?: boolean
  className?: string
}

export function ProgressBar({
  active,
  message,
  progress: explicitProgress,
  fixedTop = false,
  className = '',
}: ProgressBarProps) {
  const [simulatedProgress, setSimulatedProgress] = useState<number>(10)

  useEffect(() => {
    if (!active) {
      setSimulatedProgress(0)
      return
    }

    // Si no hay un progreso explícito, simular un avance suave y realista que frena en ~92%
    if (explicitProgress === undefined) {
      setSimulatedProgress(15)
      const interval = window.setInterval(() => {
        setSimulatedProgress((prev) => {
          if (prev < 40) return prev + Math.floor(Math.random() * 8 + 4)
          if (prev < 75) return prev + Math.floor(Math.random() * 5 + 2)
          if (prev < 90) return prev + Math.floor(Math.random() * 2 + 1)
          if (prev < 96) return prev + 0.5
          return prev
        })
      }, 350)
      return () => window.clearInterval(interval)
    }
  }, [active, explicitProgress])

  if (!active) return null

  const pct = explicitProgress !== undefined
    ? Math.min(100, Math.max(0, explicitProgress))
    : Math.min(96, Math.max(10, Math.round(simulatedProgress)))

  if (fixedTop) {
    return (
      <div
        className={`global-top-progress-container ${className}`}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-label={message || 'Procesando tarea...'}
      >
        <div
          className="global-top-progress-bar"
          style={{ width: `${pct}%` }}
        >
          <div className="global-top-progress-glow" />
        </div>
        {message && (
          <div className="global-top-progress-chip">
            <span className="global-progress-spinner" />
            <span className="global-progress-text">{message}</span>
            <span className="global-progress-pct">{pct}%</span>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={`linear-progress-wrapper ${className}`}>
      <div className="linear-progress-header">
        {message && <span className="linear-progress-label">{message}</span>}
        <span className="linear-progress-pct">{pct}%</span>
      </div>
      <div
        className="linear-progress-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
      >
        <div
          className="linear-progress-fill"
          style={{ width: `${pct}%` }}
        >
          <div className="linear-progress-shimmer" />
        </div>
      </div>
    </div>
  )
}
