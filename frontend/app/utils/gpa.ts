// What-if GPA arithmetic: a credit-weighted average of grade points.

export interface PlannedCourse {
  name: string
  credits: number
  points: number
}

/** Common four-point letter scale; the simulator also accepts raw points. */
export const LETTER_POINTS: Record<string, number> = {
  'A+': 4.0,
  'A': 4.0,
  'A-': 3.7,
  'B+': 3.3,
  'B': 3.0,
  'B-': 2.7,
  'C+': 2.3,
  'C': 2.0,
  'C-': 1.7,
  'D': 1.0,
  'F': 0,
}

export function projectGpa(currentGpa: number | null, currentCredits: number | null, planned: PlannedCourse[]): number | null {
  const valid = planned.filter(course => course.credits > 0 && course.points >= 0)
  const baseCredits = currentGpa !== null && currentCredits ? currentCredits : 0
  const base = baseCredits * (currentGpa ?? 0)
  const addedCredits = valid.reduce((sum, course) => sum + course.credits, 0)
  const added = valid.reduce((sum, course) => sum + course.credits * course.points, 0)
  const total = baseCredits + addedCredits
  return total > 0 ? Math.round(((base + added) / total) * 1000) / 1000 : null
}

/** Average grade points needed in `credits` more credits to reach `target`. */
export function pointsNeeded(currentGpa: number, currentCredits: number, credits: number, target: number): number | null {
  if (credits <= 0) return null
  const needed = (target * (currentCredits + credits) - currentGpa * currentCredits) / credits
  return Math.round(needed * 100) / 100
}
