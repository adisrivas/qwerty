import { describe, expect, it } from 'vitest'
import {
  addDays,
  clampDate,
  fmtCompact,
  fmtMinutes,
  fmtPct,
  fmtSignedMW,
  ukDate,
  ukDayLabel,
  ukTime,
} from '../lib/format'

describe('number formatting', () => {
  it('signs MW values with a true minus and leaves zero unsigned', () => {
    expect(fmtSignedMW(1730.4)).toBe('+1,730 MW')
    expect(fmtSignedMW(-420)).toBe('−420 MW')
    expect(fmtSignedMW(0.2)).toBe('0 MW')
  })
  it('compacts axis ticks', () => {
    expect(fmtCompact(12000)).toBe('12K')
    expect(fmtCompact(-4500)).toBe('−4.5K')
    expect(fmtCompact(500)).toBe('500')
  })
  it('formats percentages with one decimal', () => {
    expect(fmtPct(18.249)).toBe('18.2%')
  })
  it('formats minutes as hours and minutes', () => {
    expect(fmtMinutes(20)).toBe('20 min')
    expect(fmtMinutes(-155)).toBe('2h 35m')
    expect(fmtMinutes(120)).toBe('2h')
  })
})

describe('date and time formatting', () => {
  it('renders instants in UK local time', () => {
    expect(ukTime('2026-01-15T09:30:00Z')).toBe('09:30')
    // British Summer Time: 09:30 UTC is 10:30 local.
    expect(ukTime('2026-07-15T09:30:00Z')).toBe('10:30')
  })
  it('renders calendar dates', () => {
    expect(ukDate('2026-01-15')).toBe('Thu 15 Jan 2026')
    expect(ukDayLabel('2026-01-05')).toBe('5 Jan')
  })
  it('does date arithmetic across month ends', () => {
    expect(addDays('2026-01-31', 1)).toBe('2026-02-01')
    expect(addDays('2026-01-01', -1)).toBe('2025-12-31')
  })
  it('clamps dates to a range', () => {
    expect(clampDate('2025-12-01', '2026-01-01', '2026-01-31')).toBe('2026-01-01')
    expect(clampDate('2026-02-09', '2026-01-01', '2026-01-31')).toBe('2026-01-31')
    expect(clampDate('2026-01-15', '2026-01-01', '2026-01-31')).toBe('2026-01-15')
  })
})
