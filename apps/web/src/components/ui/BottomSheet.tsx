import React, { useState } from 'react'

export type BottomSheetSnap = 'collapsed' | 'half' | 'full'

interface BottomSheetProps {
  snap?: BottomSheetSnap
  onSnapChange?: (snap: BottomSheetSnap) => void
  headerTitle?: React.ReactNode
  headerAction?: React.ReactNode
  children: React.ReactNode
  className?: string
}

export function BottomSheet({
  snap: controlledSnap,
  onSnapChange,
  headerTitle,
  headerAction,
  children,
  className = '',
}: BottomSheetProps) {
  const [internalSnap, setInternalSnap] = useState<BottomSheetSnap>('collapsed')
  const snap = controlledSnap ?? internalSnap

  const handleToggle = () => {
    let next: BottomSheetSnap = 'half'
    if (snap === 'collapsed') next = 'half'
    else if (snap === 'half') next = 'full'
    else next = 'collapsed'

    setInternalSnap(next)
    onSnapChange?.(next)
  }

  return (
    <div className={`ui-bottom-sheet snap-${snap} ${className}`}>
      {/* Tirador táctil accesible */}
      <button
        type="button"
        className="ui-sheet-handle-btn"
        onClick={handleToggle}
        aria-label="Ajustar altura de la hoja inferior"
      >
        <div className="ui-sheet-handle-bar" />
      </button>

      {(headerTitle || headerAction) && (
        <div className="ui-sheet-header">
          <div className="ui-sheet-header-title">{headerTitle}</div>
          {headerAction && <div className="ui-sheet-header-action">{headerAction}</div>}
        </div>
      )}

      <div className="ui-sheet-body">
        {children}
      </div>
    </div>
  )
}
