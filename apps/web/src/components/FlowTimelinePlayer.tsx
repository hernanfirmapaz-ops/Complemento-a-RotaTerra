import { useEffect } from 'react'
import type { RunoffTimelineOut } from '../types/api'

interface Props {
  timeline: RunoffTimelineOut
  currentStep: number
  playing: boolean
  speed: number
  showParticles: boolean
  onStepChange: (step: number) => void
  onTogglePlay: () => void
  onReset: () => void
  onSpeedChange: (speed: number) => void
  onToggleParticles: (show: boolean) => void
}

export function FlowTimelinePlayer({
  timeline,
  currentStep,
  playing,
  speed,
  showParticles,
  onStepChange,
  onTogglePlay,
  onReset,
  onSpeedChange,
  onToggleParticles,
}: Props) {
  useEffect(() => {
    if (!playing || !timeline.has_time_series || timeline.frames.length === 0)
      return
    const intervalMs = Math.max(180, Math.round(900 / speed))
    const timer = window.setInterval(() => {
      onStepChange((currentStep + 1) % timeline.frames.length)
    }, intervalMs)
    return () => window.clearInterval(timer)
  }, [playing, speed, currentStep, timeline.has_time_series, timeline.frames.length])

  const frame =
    timeline.frames[Math.min(currentStep, Math.max(0, timeline.frames.length - 1))] ??
    null

  const w = 320
  const h = 120
  const padL = 34
  const padR = 10
  const padT = 12
  const padB = 22

  const maxP = Math.max(
    1,
    ...timeline.frames.map((f) => f.interval_precipitation_mm),
  )
  const maxTransit = Math.max(
    0.1,
    ...timeline.frames.map((f) => f.active_transit_lamina_mm),
  )

  return (
    <div className="card">
      <div className="card-header">
        <h4>Animación temporal (Fase 3 · Hietograma + MFD)</h4>
        <label className="checkbox-row" style={{ marginBottom: 0 }}>
          <input
            type="checkbox"
            checked={showParticles}
            onChange={(e) => onToggleParticles(e.target.checked)}
          />
          <span>Partículas 3D</span>
        </label>
      </div>

      {!timeline.has_time_series ? (
        <div className="alert alert-advertencia">
          {timeline.warnings[0] ??
            'Este escenario usa lluvia acumulada sin serie temporal CSV. Las partículas muestran solo las rutas topográficas potenciales.'}
        </div>
      ) : (
        <>
          <div className="player-controls">
            <button className="btn-primary" onClick={onTogglePlay}>
              {playing ? '⏸ Pausar' : '▶ Reproducir'}
            </button>
            <button className="btn-secondary" onClick={onReset}>
              ⏮ Inicio
            </button>
            <select
              value={speed}
              onChange={(e) => onSpeedChange(Number(e.target.value))}
              aria-label="Velocidad de reproducción"
            >
              <option value={0.5}>0,5×</option>
              <option value={1}>1×</option>
              <option value={2}>2×</option>
              <option value={4}>4×</option>
            </select>
          </div>

          <input
            type="range"
            className="timeline-slider"
            min={0}
            max={Math.max(0, timeline.frames.length - 1)}
            value={currentStep}
            onChange={(e) => onStepChange(Number(e.target.value))}
          />

          <svg
            viewBox={`0 0 ${w} ${h}`}
            className="profile-svg"
            role="img"
            aria-label="Hietograma de lluvia y curva de escorrentía en tránsito"
          >
            {timeline.frames.map((f, idx) => {
              const n = timeline.frames.length
              const bw = (w - padL - padR) / n
              const x = padL + idx * bw
              const bh =
                ((h - padT - padB) * f.interval_precipitation_mm) / maxP
              const y = h - padB - bh
              const isCur = idx === currentStep
              return (
                <g key={f.step_index}>
                  <rect
                    x={x + 1}
                    y={y}
                    width={Math.max(2, bw - 2)}
                    height={Math.max(0, bh)}
                    fill={
                      isCur
                        ? '#38bdf8'
                        : f.is_recession
                          ? 'rgba(148,163,184,0.2)'
                          : 'rgba(56,189,248,0.42)'
                    }
                  />
                  {isCur && (
                    <line
                      x1={x + bw / 2}
                      y1={padT}
                      x2={x + bw / 2}
                      y2={h - padB}
                      stroke="#f59e0b"
                      strokeWidth="1.5"
                    />
                  )}
                </g>
              )
            })}
            {/* Polilínea de lámina en tránsito */}
            <path
              d={timeline.frames
                .map((f, idx) => {
                  const n = timeline.frames.length
                  const bw = (w - padL - padR) / n
                  const cx = padL + idx * bw + bw / 2
                  const cy =
                    h -
                    padB -
                    ((h - padT - padB) * f.active_transit_lamina_mm) /
                      maxTransit
                  return `${idx === 0 ? 'M' : 'L'}${cx.toFixed(1)},${cy.toFixed(1)}`
                })
                .join(' ')}
              fill="none"
              stroke="#34d399"
              strokeWidth="2"
            />
            <text x={4} y={padT + 8} className="svg-label">
              {maxP.toFixed(0)} mm
            </text>
            <text x={padL} y={h - 6} className="svg-label">
              Paso 1
            </text>
            <text x={w - padR - 55} y={h - 6} className="svg-label">
              Paso {timeline.frames.length}
            </text>
          </svg>

          {frame && (
            <dl className="kv-grid">
              <div>
                <dt>Paso / instante</dt>
                <dd>
                  #{frame.step_index + 1}/{timeline.total_steps}{' '}
                  {frame.is_recession ? '(Recesión)' : ''}
                </dd>
              </div>
              <div>
                <dt>Hora intervalo</dt>
                <dd>{frame.timestamp.slice(11, 19) || frame.timestamp}</dd>
              </div>
              <div>
                <dt>Lluvia ΔP / P acum.</dt>
                <dd>
                  {frame.interval_precipitation_mm.toFixed(1)} /{' '}
                  {frame.cumulative_precipitation_mm.toFixed(1)} mm
                </dd>
              </div>
              <div>
                <dt>Pérdidas Ia+F acum.</dt>
                <dd>{frame.cumulative_infiltration_losses_mm.toFixed(1)} mm</dd>
              </div>
              <div>
                <dt>Excedente ΔQ / Q acum.</dt>
                <dd>
                  {frame.interval_runoff_generated_mm.toFixed(2)} /{' '}
                  {frame.cumulative_runoff_generated_mm.toFixed(2)} mm
                </dd>
              </div>
              <div>
                <dt>En tránsito activo</dt>
                <dd>
                  {frame.active_transit_lamina_mm.toFixed(2)} mm (
                  {frame.active_transit_volume_m3.toFixed(0)} m³)
                </dd>
              </div>
              <div>
                <dt>Retenido en bajos</dt>
                <dd>
                  {frame.depression_retained_mm.toFixed(2)} mm (
                  {frame.depression_retained_volume_m3.toFixed(0)} m³)
                </dd>
              </div>
              <div>
                <dt>Salida acum. lote</dt>
                <dd>
                  {frame.cumulative_outflow_mm.toFixed(2)} mm (
                  {frame.cumulative_outflow_m3.toFixed(0)} m³)
                </dd>
              </div>
            </dl>
          )}
        </>
      )}
    </div>
  )
}
