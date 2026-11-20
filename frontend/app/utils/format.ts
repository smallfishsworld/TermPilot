// Human-friendly formatting shared by the views. The interface is English, so dates are too.

const LOCALE = 'en-US'

const dateTime = new Intl.DateTimeFormat(LOCALE, { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
const dateOnly = new Intl.DateTimeFormat(LOCALE, { weekday: 'long', month: 'long', day: 'numeric' })
const shortDate = new Intl.DateTimeFormat(LOCALE, { month: 'short', day: 'numeric' })

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTime.format(new Date(iso)) : '—'
}

export function formatLongDate(day: string | Date): string {
  const value = typeof day === 'string' ? new Date(`${day.slice(0, 10)}T12:00:00`) : day
  return dateOnly.format(value)
}

export function formatShortDate(iso: string): string {
  return shortDate.format(new Date(iso.length === 10 ? `${iso}T12:00:00` : iso))
}

/** "in 3 h", "2 days ago", "tomorrow" ... relative to `now`. */
export function relativeTime(iso: string, now: Date = new Date()): string {
  const diffMinutes = Math.round((new Date(iso).getTime() - now.getTime()) / 60_000)
  const abs = Math.abs(diffMinutes)
  const future = diffMinutes >= 0
  let text: string
  if (abs < 1) return 'now'
  if (abs < 60) text = `${abs} min`
  else if (abs < 60 * 24) text = `${Math.round(abs / 60)} h`
  else if (abs < 60 * 24 * 2) return future ? 'tomorrow' : 'yesterday'
  else text = `${Math.round(abs / (60 * 24))} days`
  return future ? `in ${text}` : `${text} ago`
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} kB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours} h ${rest} min` : `${hours} h`
}

/** Local "YYYY-MM-DDTHH:MM" for <input type="datetime-local">. */
export function toLocalInput(iso: string): string {
  const date = new Date(iso)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** A datetime-local value with the browser's UTC offset, as the API requires. */
export function fromLocalInput(value: string): string {
  const date = new Date(value)
  const offset = -date.getTimezoneOffset()
  const sign = offset >= 0 ? '+' : '-'
  const pad = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, '0')
  return `${value.length === 16 ? `${value}:00` : value}${sign}${pad(offset / 60)}:${pad(offset % 60)}`
}

export function greeting(hour: number): string {
  if (hour < 5) return 'Working late'
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}
