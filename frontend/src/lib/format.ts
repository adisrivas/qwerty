export const UK_TZ = 'Europe/London'

const integer = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 })
const oneDecimal = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 1 })

/** `12,345` */
export function fmtInt(value: number): string {
  return integer.format(value)
}

/** `1,730 MW` */
export function fmtMW(value: number): string {
  return `${integer.format(value)} MW`
}

/** `+1,730 MW` / `−420 MW`. Zero is unsigned. */
export function fmtSignedMW(value: number): string {
  const rounded = Math.round(value)
  if (rounded === 0) return '0 MW'
  return `${rounded > 0 ? '+' : '−'}${integer.format(Math.abs(rounded))} MW`
}

/** `+12,345 MWh` */
export function fmtSignedMWh(value: number): string {
  const rounded = Math.round(value)
  if (rounded === 0) return '0 MWh'
  return `${rounded > 0 ? '+' : '−'}${integer.format(Math.abs(rounded))} MWh`
}

/** `123,456 MWh` */
export function fmtMWh(value: number): string {
  return `${integer.format(value)} MWh`
}

/** `18.2%` */
export function fmtPct(value: number): string {
  return `${oneDecimal.format(value)}%`
}

/** Axis tick: `12K`, `−4K`, `500` */
export function fmtCompact(value: number): string {
  const abs = Math.abs(value)
  const sign = value < 0 ? '−' : ''
  if (abs >= 1000) return `${sign}${oneDecimal.format(abs / 1000).replace(/\.0$/, '')}K`
  return `${sign}${integer.format(abs)}`
}

const timeFmt = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: UK_TZ,
})
const dateFmt = new Intl.DateTimeFormat('en-GB', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  timeZone: UK_TZ,
})
const shortDateFmt = new Intl.DateTimeFormat('en-GB', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  timeZone: UK_TZ,
})
const dateTimeFmt = new Intl.DateTimeFormat('en-GB', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: UK_TZ,
})

/** `09:30` in UK local time from an ISO instant. */
export function ukTime(iso: string): string {
  return timeFmt.format(new Date(iso))
}

/** `Thu 15 Jan, 09:30` in UK local time from an ISO instant. */
export function ukDateTime(iso: string): string {
  return dateTimeFmt.format(new Date(iso))
}

/** `Thu 15 Jan 2026` from a `YYYY-MM-DD` date. */
export function ukDate(date: string): string {
  return stripCommas(dateFmt.format(parseDate(date)))
}

/** `Thu 15 Jan` from a `YYYY-MM-DD` date. */
export function ukShortDate(date: string): string {
  return stripCommas(shortDateFmt.format(parseDate(date)))
}

function stripCommas(text: string): string {
  return text.replace(/,/g, '')
}

/** `15 Jan` day label for axes from a `YYYY-MM-DD` date. */
export function ukDayLabel(date: string): string {
  const [, month, day] = date.split('-')
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ]
  return `${Number(day)} ${months[Number(month) - 1] ?? ''}`
}

/** `YYYY-MM-DD` as midnight UTC. */
export function parseDate(date: string): Date {
  return new Date(`${date}T00:00:00Z`)
}

/** `YYYY-MM-DD` shifted by `days`. */
export function addDays(date: string, days: number): string {
  const d = parseDate(date)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

/** `2h 20m` / `20 min` from a minute count (absolute value). */
export function fmtMinutes(minutes: number): string {
  const abs = Math.abs(Math.round(minutes))
  if (abs < 60) return `${abs} min`
  const h = Math.floor(abs / 60)
  const m = abs % 60
  return m === 0 ? `${h}h` : `${h}h ${m}m`
}

/** Clamp a `YYYY-MM-DD` string into an inclusive range. */
export function clampDate(date: string, min: string, max: string): string {
  if (date < min) return min
  if (date > max) return max
  return date
}

export const DATE_RE = /^\d{4}-\d{2}-\d{2}$/
export const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/
