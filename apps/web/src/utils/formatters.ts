/**
 * Funciones de formateo agronómico e hidrológico en español para el visor 3D.
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
