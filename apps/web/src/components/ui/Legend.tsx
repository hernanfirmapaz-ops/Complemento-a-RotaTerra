export type LegendType = 'water' | 'relief' | 'erosion' | 'ndvi' | 'custom'

interface LegendProps {
  title: string
  minLabel: string | number
  maxLabel: string | number
  unit?: string
  type?: LegendType
  customGradient?: string
  className?: string
}

const GRADIENT_MAP: Record<LegendType, string> = {
  water: 'linear-gradient(90deg, #DCEBFA 0%, #2B7BD6 50%, #0B3D7A 100%)',
  relief: 'linear-gradient(90deg, #F2EEE6 0%, #A89F8E 50%, #5C5446 100%)',
  erosion: 'linear-gradient(90deg, #FDF1D8 0%, #E08A2E 50%, #9E2A12 100%)',
  ndvi: 'linear-gradient(90deg, #EEF5E9 0%, #7FB069 50%, #2E6B2F 100%)',
  custom: 'linear-gradient(90deg, #10b981, #38bdf8)',
}

export function Legend({
  title,
  minLabel,
  maxLabel,
  unit,
  type = 'water',
  customGradient,
  className = '',
}: LegendProps) {
  const gradient = customGradient || GRADIENT_MAP[type]

  return (
    <div className={`ui-legend ${className}`} role="region" aria-label={`Leyenda: ${title}`}>
      <span className="ui-legend-title">{title}</span>
      <div
        className="ui-legend-bar"
        style={{ background: gradient }}
        aria-hidden="true"
      />
      <div className="ui-legend-labels">
        <span className="ui-legend-min">
          {minLabel} {unit}
        </span>
        <span className="ui-legend-max">
          {maxLabel} {unit}
        </span>
      </div>
    </div>
  )
}
