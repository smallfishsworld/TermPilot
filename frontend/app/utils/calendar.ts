// Date arithmetic for the timetable. Dates are plain "YYYY-MM-DD" strings
// interpreted in the browser's local time; times are "HH:MM".

export const WEEKDAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] as const
export const WEEKDAY_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const

export function parseDay(value: string): Date {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return new Date(year!, (month ?? 1) - 1, day ?? 1)
}

export function formatDay(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function addDays(day: string, amount: number): string {
  const date = parseDay(day)
  date.setDate(date.getDate() + amount)
  return formatDay(date)
}

/** ISO weekday: 1 = Monday ... 7 = Sunday. */
export function isoWeekday(day: string): number {
  const weekday = parseDay(day).getDay()
  return weekday === 0 ? 7 : weekday
}

export function mondayOf(day: string): string {
  return addDays(day, 1 - isoWeekday(day))
}

export function daysBetween(from: string, to: string): number {
  return Math.round((parseDay(to).getTime() - parseDay(from).getTime()) / 86_400_000)
}

/** Teaching week (1-based) of `day` for a term whose first Monday is `termStart`. */
export function teachingWeek(termStart: string, day: string): number {
  return Math.floor(daysBetween(mondayOf(termStart), day) / 7) + 1
}

export function dateOfWeek(termStart: string, week: number, weekday: number): string {
  return addDays(mondayOf(termStart), (week - 1) * 7 + weekday - 1)
}

export function minutesOf(time: string): number {
  const [hours, minutes] = time.split(':').map(Number)
  return (hours ?? 0) * 60 + (minutes ?? 0)
}

export function clockOf(minutes: number): string {
  const safe = Math.max(0, Math.min(24 * 60 - 1, Math.round(minutes)))
  return `${String(Math.floor(safe / 60)).padStart(2, '0')}:${String(safe % 60).padStart(2, '0')}`
}

/** Whether an entry with `weeks` (empty = every week) takes place in `week`. */
export function occursInWeek(weeks: number[], week: number): boolean {
  return weeks.length === 0 || weeks.includes(week)
}

export interface Placed<T> {
  item: T
  lane: number
  lanes: number
}

/**
 * Assign overlapping blocks of one day to side-by-side lanes so none hide
 * each other. Each cluster of mutually overlapping blocks shares a lane count.
 */
export function layoutLanes<T extends { starts_at: string, ends_at: string }>(items: T[]): Placed<T>[] {
  const sorted = [...items].sort((a, b) => minutesOf(a.starts_at) - minutesOf(b.starts_at))
  const placed: Placed<T>[] = []
  let cluster: Placed<T>[] = []
  let clusterEnd = -1
  let laneEnds: number[] = []

  const closeCluster = () => {
    const lanes = Math.max(1, laneEnds.length)
    for (const entry of cluster) entry.lanes = lanes
    placed.push(...cluster)
    cluster = []
    laneEnds = []
  }

  for (const item of sorted) {
    const start = minutesOf(item.starts_at)
    const end = minutesOf(item.ends_at)
    if (cluster.length && start >= clusterEnd) closeCluster()
    let lane = laneEnds.findIndex(laneEnd => laneEnd <= start)
    if (lane === -1) {
      lane = laneEnds.length
      laneEnds.push(end)
    }
    else {
      laneEnds[lane] = end
    }
    cluster.push({ item, lane, lanes: 1 })
    clusterEnd = Math.max(clusterEnd, end)
  }
  if (cluster.length) closeCluster()
  return placed
}

/** "1-3, 5" style summary of a week list. */
export function describeWeeks(weeks: number[]): string {
  if (!weeks.length) return 'every week'
  const sorted = [...new Set(weeks)].sort((a, b) => a - b)
  const parts: string[] = []
  let start = sorted[0]!
  let previous = start
  for (const week of [...sorted.slice(1), Number.NaN]) {
    if (week === previous + 1) {
      previous = week
      continue
    }
    parts.push(start === previous ? `${start}` : `${start}-${previous}`)
    start = week
    previous = week
  }
  return parts.join(', ')
}

/** Parse "1-8, 10, 12-16" into week numbers; invalid parts are ignored. */
export function parseWeekList(text: string, limit = 30): number[] {
  const weeks = new Set<number>()
  for (const part of text.split(/[,，\s]+/)) {
    const match = part.match(/^(\d{1,2})(?:-(\d{1,2}))?$/)
    if (!match) continue
    const from = Number(match[1])
    const to = Number(match[2] ?? match[1])
    for (let week = Math.min(from, to); week <= Math.max(from, to); week++) {
      if (week >= 1 && week <= limit) weeks.add(week)
    }
  }
  return [...weeks].sort((a, b) => a - b)
}
