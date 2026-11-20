import { describe, expect, it } from 'vitest'
import { addDays, dateOfWeek, describeWeeks, isoWeekday, layoutLanes, mondayOf, occursInWeek, parseWeekList, teachingWeek } from '../app/utils/calendar'

describe('dates and teaching weeks', () => {
  it('finds weekdays and Mondays', () => {
    expect(isoWeekday('2026-10-14')).toBe(3)
    expect(isoWeekday('2026-10-18')).toBe(7)
    expect(mondayOf('2026-10-18')).toBe('2026-10-12')
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
  })

  it('maps dates to teaching weeks and back', () => {
    expect(teachingWeek('2026-09-07', '2026-09-07')).toBe(1)
    expect(teachingWeek('2026-09-07', '2026-10-14')).toBe(6)
    expect(teachingWeek('2026-09-09', '2026-09-14')).toBe(2) // a mid-week start still counts from its Monday
    expect(dateOfWeek('2026-09-07', 6, 3)).toBe('2026-10-14')
  })

  it('handles week lists', () => {
    expect(occursInWeek([], 9)).toBe(true)
    expect(occursInWeek([1, 3, 5], 4)).toBe(false)
    expect(parseWeekList('1-4, 6，8-9 99 x')).toEqual([1, 2, 3, 4, 6, 8, 9])
    expect(describeWeeks([5, 1, 2, 3, 8, 9])).toBe('1-3, 5, 8-9')
    expect(describeWeeks([])).toBe('every week')
  })
})

describe('layoutLanes', () => {
  const block = (id: number, starts_at: string, ends_at: string) => ({ id, starts_at, ends_at })

  it('keeps separate blocks in one lane', () => {
    const placed = layoutLanes([block(1, '08:00', '09:00'), block(2, '09:00', '10:00')])
    expect(placed.map(p => [p.item.id, p.lane, p.lanes])).toEqual([[1, 0, 1], [2, 0, 1]])
  })

  it('puts overlapping blocks side by side and reuses free lanes', () => {
    const placed = layoutLanes([block(1, '08:00', '10:00'), block(2, '09:00', '11:00'), block(3, '10:00', '11:30')])
    expect(placed.map(p => [p.item.id, p.lane, p.lanes])).toEqual([[1, 0, 2], [2, 1, 2], [3, 0, 2]])
  })
})
