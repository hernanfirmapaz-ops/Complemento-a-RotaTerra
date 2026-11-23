import { describe, it, expect } from 'vitest'
import {
  formatAmcLabel,
  formatDecimal,
  formatDistance,
  formatHa,
} from '../formatters'

describe('formatAmcLabel', () => {
  it('formatea DRY a seca (AMC I)', () => {
    expect(formatAmcLabel('dry')).toBe('seca (AMC I)')
    expect(formatAmcLabel('DRY')).toBe('seca (AMC I)')
    expect(formatAmcLabel('amc_i')).toBe('seca (AMC I)')
  })

  it('formatea MEDIUM a media (AMC II)', () => {
    expect(formatAmcLabel('medium')).toBe('media (AMC II)')
    expect(formatAmcLabel('MEDIUM')).toBe('media (AMC II)')
  })

  it('formatea WET a húmeda (AMC III)', () => {
    expect(formatAmcLabel('wet')).toBe('húmeda (AMC III)')
    expect(formatAmcLabel('WET')).toBe('húmeda (AMC III)')
  })

  it('maneja valores vacíos o nulos', () => {
    expect(formatAmcLabel(null)).toBe('Sin dato')
    expect(formatAmcLabel(undefined)).toBe('Sin dato')
    expect(formatAmcLabel('')).toBe('Sin dato')
  })
})

describe('formatters con coma decimal (Issue #84)', () => {
  it('formatDecimal usa coma como separador decimal', () => {
    expect(formatDecimal(126.2, 1)).toBe('126,2')
    expect(formatDecimal(1.86, 2)).toBe('1,86')
    expect(formatDecimal(0, 1)).toBe('0,0')
  })

  it('formatHa formatea hectáreas con coma decimal', () => {
    expect(formatHa(126.2)).toBe('126,2 ha')
    expect(formatHa(126.234, 1)).toBe('126,2 ha')
    expect(formatHa(0)).toBe('0 ha')
    expect(formatHa(-5)).toBe('0 ha')
  })

  it('formatDistance formatea en metros o kilómetros con coma decimal', () => {
    expect(formatDistance(1860, 2)).toBe('1,86 km')
    expect(formatDistance(450)).toBe('450 m')
    expect(formatDistance(0)).toBe('0 m')
  })
})
