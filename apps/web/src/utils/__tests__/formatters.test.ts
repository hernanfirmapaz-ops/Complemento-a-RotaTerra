import { describe, it, expect } from 'vitest'
import { formatAmcLabel } from '../formatters'

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
