import type { ProfileOut } from '../types/api'

interface Props {
  profile: ProfileOut
  onClear: () => void
}

export function ProfileChart({ profile, onClear }: Props) {
  const valid = profile.samples.filter(
    (s): s is { distance_m: number; elevation_m: number; lon: number; lat: number } =>
      s.elevation_m !== null,
  )

  if (valid.length < 2) {
    return (
      <div className="card">
        <div className="card-header">
          <h4>Perfil altimétrico</h4>
          <button className="btn-ghost" onClick={onClear}>
            Limpiar
          </button>
        </div>
        <p className="muted">
          La línea trazada no intersecta suficientes celdas con dato de
          elevación.
        </p>
      </div>
    )
  }

  const w = 320
  const h = 150
  const padL = 42
  const padR = 12
  const padT = 14
  const padB = 26

  const maxD = Math.max(1, profile.summary.length_m)
  const minZ = Math.min(...valid.map((s) => s.elevation_m))
  const maxZ = Math.max(...valid.map((s) => s.elevation_m))
  const spanZ = Math.max(0.5, maxZ - minZ)

  const xOf = (d: number) => padL + ((w - padL - padR) * d) / maxD
  const yOf = (z: number) =>
    h - padB - ((h - padT - padB) * (z - minZ)) / spanZ

  const pathD = valid
    .map(
      (s, idx) =>
        `${idx === 0 ? 'M' : 'L'}${xOf(s.distance_m).toFixed(1)},${yOf(
          s.elevation_m,
        ).toFixed(1)}`,
    )
    .join(' ')

  const areaD = `${pathD} L${xOf(valid[valid.length - 1].distance_m).toFixed(
    1,
  )},${h - padB} L${xOf(valid[0].distance_m).toFixed(1)},${h - padB} Z`

  return (
    <div className="card">
      <div className="card-header">
        <h4>Perfil altimétrico (escala real 1×)</h4>
        <button className="btn-ghost" onClick={onClear}>
          Limpiar
        </button>
      </div>

      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="profile-svg"
        role="img"
        aria-label="Perfil de elevación a lo largo de la línea"
      >
        <path d={areaD} fill="rgba(52, 211, 153, 0.18)" />
        <path d={pathD} fill="none" stroke="#34d399" strokeWidth="2" />
        <line
          x1={padL}
          y1={h - padB}
          x2={w - padR}
          y2={h - padB}
          stroke="#475569"
        />
        <line x1={padL} y1={padT} x2={padL} y2={h - padB} stroke="#475569" />
        <text x={4} y={padT + 8} className="svg-label">
          {maxZ.toFixed(1)} m
        </text>
        <text x={4} y={h - padB} className="svg-label">
          {minZ.toFixed(1)} m
        </text>
        <text x={padL} y={h - 6} className="svg-label">
          0 m
        </text>
        <text x={w - padR - 48} y={h - 6} className="svg-label">
          {profile.summary.length_m.toFixed(0)} m
        </text>
      </svg>

      <dl className="kv-grid">
        <div>
          <dt>Longitud</dt>
          <dd>{profile.summary.length_m.toFixed(1)} m</dd>
        </div>
        <div>
          <dt>Paso muestreo</dt>
          <dd>{profile.summary.step_m.toFixed(1)} m</dd>
        </div>
        <div>
          <dt>Cota mín / máx</dt>
          <dd>
            {profile.summary.min_m?.toFixed(2)} /{' '}
            {profile.summary.max_m?.toFixed(2)} m
          </dd>
        </div>
        <div>
          <dt>Desnivel neto</dt>
          <dd>
            {profile.summary.start_end_diff_m !== null
              ? `${profile.summary.start_end_diff_m > 0 ? '+' : ''}${profile.summary.start_end_diff_m.toFixed(2)} m`
              : 's/d'}
          </dd>
        </div>
        <div>
          <dt>Pendiente media |S|</dt>
          <dd>
            {profile.summary.mean_abs_slope_pct !== null
              ? `${profile.summary.mean_abs_slope_pct.toFixed(2)} %`
              : 's/d'}
          </dd>
        </div>
        <div>
          <dt>Píxel DEM</dt>
          <dd>{profile.pixel_size_m.toFixed(1)} m</dd>
        </div>
      </dl>
    </div>
  )
}
