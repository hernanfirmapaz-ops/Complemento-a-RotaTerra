import React from 'react'
import { Icon } from './Icon'

interface DetailsProps {
  summary: string
  subsummary?: string
  defaultOpen?: boolean
  children: React.ReactNode
  className?: string
}

export function Details({
  summary,
  subsummary,
  defaultOpen = false,
  children,
  className = '',
}: DetailsProps) {
  return (
    <details className={`ui-details ${className}`} open={defaultOpen}>
      <summary className="ui-details-summary">
        <span className="ui-details-chevron">
          <Icon name="chevron-right" size={16} />
        </span>
        <span className="ui-details-title">{summary}</span>
        {subsummary && <span className="ui-details-sub">{subsummary}</span>}
      </summary>
      <div className="ui-details-content">
        {children}
      </div>
    </details>
  )
}
