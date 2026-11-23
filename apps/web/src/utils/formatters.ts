/**
 * Funciones de formateo agronómico e hidrológico en español para el visor 3D y delimitador de lotes.
 */

/**
 * Convierte códigos de humedad antecedente del suelo (AMC) a texto descriptivo en español.
 * - 'dry' / 'amc_i' -> 'seca (AMC I)'
 * - 'medium' / 'amc_ii' -> 'media (AMC II)'
 * - 'wet' / 'amc_iii' -> 'húmeda (AMC III)'
 */
export function formatAmcLabel(amc?: string | null): string {
  if (!amc) return 'Sin dato'
  const lower = amc.trim().toLowerCase()
  if (lower === 'dry' || lower === 'amc_i' || lower === 'amc i' || lower === 'i') {
    return 'seca (AMC I)'
  }
  if (lower === 'medium' || lower === 'amc_ii' || lower === 'amc ii' || lower === 'ii' || lower === 'normal') {
    return 'media (AMC II)'
  }
  if (lower === 'wet' || lower === 'amc_iii' || lower === 'amc iii' || lower === 'iii') {
    return 'húmeda (AMC III)'
  }
  return amc
}

/**
 * Formatea un número decimal con coma decimal según convención en español / Argentina (Issue #84).
 * Ej: 126.2 -> "126,2"
 */
export function formatDecimal(val: number, decimals: number = 1): string {
  if (isNaN(val) || !isFinite(val)) return '0'
  return val.toFixed(decimals).replace('.', ',')
}

/**
 * Formatea superficies en hectáreas con coma decimal.
 * Ej: 126.23 -> "126,2 ha"
 */
export function formatHa(ha: number, decimals: number = 1): string {
  if (ha <= 0 || isNaN(ha)) return '0 ha'
  return `${formatDecimal(ha, decimals)} ha`
}

/**
 * Formatea distancias y dimensiones en metros o kilómetros con coma decimal.
 * Ej: 1860 m -> "1,86 km", 450 m -> "450 m"
 */
export function formatDistance(m: number, decimals: number = 2): string {
  if (m <= 0 || isNaN(m)) return '0 m'
  if (m >= 1000) {
    return `${formatDecimal(m / 1000, decimals)} km`
  }
  return `${m.toFixed(0)} m`
}
