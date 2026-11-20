import { Icon, type IconName } from './Icon'

export interface OptionListItem {
  id: string
  title: string
  subtitle?: string
  meta?: string
  icon?: IconName
  badge?: string
  disabled?: boolean
  selected?: boolean
}

interface OptionListProps {
  items: OptionListItem[]
  selectedId?: string
  onSelect?: (item: OptionListItem) => void
  showChevron?: boolean
  className?: string
}

export function OptionList({
  items,
  selectedId,
  onSelect,
  showChevron = true,
  className = '',
}: OptionListProps) {
  return (
    <div className={`ui-option-list ${className}`} role="listbox">
      {items.map((item) => {
        const isSelected = item.selected ?? (selectedId === item.id)
        return (
          <button
            key={item.id}
            type="button"
            className={`ui-option-item ${isSelected ? 'selected' : ''}`}
            onClick={() => !item.disabled && onSelect?.(item)}
            disabled={item.disabled}
            role="option"
            aria-selected={isSelected}
          >
            {item.icon && (
              <span className="ui-option-icon">
                <Icon name={item.icon} size={20} />
              </span>
            )}
            <div className="ui-option-content">
              <div className="ui-option-title-row">
                <span className="ui-option-title">{item.title}</span>
                {item.badge && <span className="ui-option-badge">{item.badge}</span>}
              </div>
              {item.subtitle && (
                <span className="ui-option-subtitle">{item.subtitle}</span>
              )}
            </div>
            {item.meta && <span className="ui-option-meta">{item.meta}</span>}
            {showChevron && !item.disabled && (
              <span className="ui-option-chevron">
                <Icon name="chevron-right" size={16} />
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
