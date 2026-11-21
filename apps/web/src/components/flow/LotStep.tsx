import React from 'react'
import type { FieldOut } from '../../types/api'
import { Button } from '../ui/Button'
import { SourceNote } from '../ui/SourceNote'
import { Icon } from '../ui/Icon'

interface LotStepProps {
  fields: FieldOut[]
  activeField: FieldOut | null
  onSelectField: (id: string) => void
  onOpenDrawer: () => void
  onFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void
  onContinue: () => void
  busy: boolean
  className?: string
}

export function LotStep({
  fields,
  activeField,
  onSelectField,
  onOpenDrawer,
  onFileUpload,
  onContinue,
  busy,
  className = '',
}: LotStepProps) {
  return (
    <div className={`lot-step ${className}`}>
      <div className="step-header">
        <h2 className="step-heading">Elegí tu lote</h2>
        <p className="step-subtext">
          Marcá las esquinas de tu terreno en el mapa o subí el archivo de tu lote catastral.
        </p>
      </div>

      <div className="lot-actions-stack">
        <Button
          variant={activeField ? 'secondary' : 'primary'}
          onClick={onOpenDrawer}
          icon="map-pin"
          disabled={busy}
          fullWidth
        >
          Dibujar en el mapa satelital
        </Button>

        <label className="ui-file-upload-label">
          <input
            type="file"
            accept=".geojson,.json,.kml,.kmz,.zip"
            onChange={onFileUpload}
            disabled={busy}
            hidden
          />
          <span className="ui-btn ui-btn-secondary ui-btn-md ui-btn-full">
            <Icon name="upload" size={18} />
            <span className="ui-btn-label">Subir archivo (KML, KMZ, GeoJSON, ZIP)</span>
          </span>
        </label>
      </div>

      {/* Si hay lotes cargados en la sesión */}
      {fields.length > 0 && (
        <div className="lot-session-list">
          <label className="field-label-text">
            Tus lotes analizados ({fields.length}):
          </label>
          <div className="lot-cards-col">
            {fields.map((f) => {
              const isSelected = activeField?.id === f.id
              return (
                <button
                  key={f.id}
                  type="button"
                  className={`lot-card-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => onSelectField(f.id)}
                >
                  <div className="lot-card-info">
                    <span className="lot-card-title">{f.name}</span>
                    <span className="lot-card-meta">
                      {f.area_ha.toFixed(1)} ha · UTM {f.utm_epsg}
                    </span>
                  </div>
                  {isSelected && (
                    <span className="lot-card-check">
                      <Icon name="check" size={16} />
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Resumen del lote activo y botón de continuación */}
      {activeField && (
        <div className="lot-active-callout">
          <div className="lot-active-summary">
            <span className="lot-active-badge">Lote seleccionado</span>
            <strong className="lot-active-name">{activeField.name}</strong>
            <span className="lot-active-ha">{activeField.area_ha.toFixed(1)} ha</span>
          </div>

          <Button
            variant="primary"
            onClick={onContinue}
            disabled={busy}
            fullWidth
          >
            Continuar a Lluvia →
          </Button>
        </div>
      )}

      <div className="step-footer-note">
        <SourceNote
          isNotice
          source=""
          disclaimer="Tu lote no se guarda en ningún servidor externo. El procesamiento se realiza de forma local y privada."
        />
      </div>
    </div>
  )
}
