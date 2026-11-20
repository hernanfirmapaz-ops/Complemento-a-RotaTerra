import { Icon } from './Icon'

interface SourceNoteProps {
  source: string
  details?: string
  disclaimer?: string
  isNotice?: boolean
  className?: string
}

export function SourceNote({
  source,
  details,
  disclaimer,
  isNotice = false,
  className = '',
}: SourceNoteProps) {
  if (isNotice) {
    return (
      <div className={`ui-notice ${className}`}>
        <p className="ui-notice-text">
          {disclaimer || source}
        </p>
      </div>
    )
  }

  return (
    <div className={`ui-source-note ${className}`}>
      <span className="ui-source-icon">
        <Icon name="info" size={14} />
      </span>
      <span className="ui-source-text">
        Fuente: <strong>{source}</strong>
        {details ? ` · ${details}` : ''}
      </span>
      {disclaimer && (
        <span className="ui-source-disclaimer">({disclaimer})</span>
      )}
    </div>
  )
}
