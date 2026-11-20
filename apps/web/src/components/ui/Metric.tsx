interface MetricProps {
  label: string
  value: string | number
  unit?: string
  /** Rango opcional cuando hay incertidumbre (ej: "18 – 22") */
  range?: string
  caption?: string
  trend?: 'positive' | 'negative' | 'neutral'
  className?: string
}

export function Metric({
  label,
  value,
  unit,
  range,
  caption,
  trend,
  className = '',
}: MetricProps) {
  return (
    <div className={`ui-metric ${trend ? `ui-metric-${trend}` : ''} ${className}`}>
      <div className="ui-metric-main">
        <span className="ui-metric-number">
          {value}
        </span>
        {unit && <span className="ui-metric-unit">{unit}</span>}
      </div>
      {range && <span className="ui-metric-range">Rango estimado: {range}</span>}
      <span className="ui-metric-label">{label}</span>
      {caption && <span className="ui-metric-caption">{caption}</span>}
    </div>
  )
}
