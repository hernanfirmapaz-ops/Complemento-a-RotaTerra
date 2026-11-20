export interface SegmentedOption<T extends string = string> {
  value: T
  label: string
  sublabel?: string
  disabled?: boolean
}

interface SegmentedProps<T extends string = string> {
  options: SegmentedOption<T>[]
  value: T
  onChange: (value: T) => void
  disabled?: boolean
  className?: string
  'aria-label'?: string
}

export function Segmented<T extends string = string>({
  options,
  value,
  onChange,
  disabled = false,
  className = '',
  'aria-label': ariaLabel = 'Control segmentado',
}: SegmentedProps<T>) {
  return (
    <div
      className={`ui-segmented ${className}`}
      role="group"
      aria-label={ariaLabel}
    >
      {options.slice(0, 4).map((opt) => {
        const isActive = opt.value === value
        const isDisabled = disabled || opt.disabled
        return (
          <button
            key={opt.value}
            type="button"
            className={`ui-segmented-btn ${isActive ? 'active' : ''}`}
            onClick={() => !isDisabled && onChange(opt.value)}
            disabled={isDisabled}
            aria-pressed={isActive}
          >
            <span className="ui-segmented-label">{opt.label}</span>
            {opt.sublabel && (
              <span className="ui-segmented-sublabel">{opt.sublabel}</span>
            )}
          </button>
        )
      })}
    </div>
  )
}
