// Shapes returned by the TermPilot API (see backend/termpilot/api/schemas.py).

export interface Features {
  demo_mode: boolean
  assistant: boolean
  library: boolean
  web_search: boolean
}

export interface Student {
  id: number
  display_name: string
  pinyin_name: string | null
  email: string | null
  phone: string | null
  gender: string | null
  birth_date: string | null
  college: string | null
  department: string | null
  class_name: string | null
  dormitory: string | null
  gpa: number | null
  gpa_rank: string | null
  interests: string | null
  term_start: string | null
  is_demo: boolean
}

export interface SessionResponse {
  token: string
  token_type: 'bearer'
  expires_in: number
  first_visit: boolean
  student: Student
}

export interface Term {
  today: string
  label: string
  academic_year: string
  start: string
  end: string
  weeks: number
  current_week: number
  in_session: boolean
}

export type EntryKind = 'course' | 'study' | 'activity' | 'meeting' | 'other'

export interface Entry {
  id: number
  title: string
  kind: EntryKind
  origin: string
  weekday: number
  starts_at: string
  ends_at: string
  first_period: number | null
  last_period: number | null
  weeks: number[]
  week_label: string | null
  location: string | null
  instructor: string | null
  notes: string | null
  color: string | null
  task_id: number | null
}

export type EntryInput = Pick<Entry, 'title' | 'kind' | 'weekday' | 'starts_at' | 'ends_at' | 'weeks'> &
  Partial<Pick<Entry, 'location' | 'instructor' | 'notes' | 'color'>>

export interface Clash {
  first_id: number
  second_id: number
  weekday: number
  weeks: number[]
  starts_at: string
  ends_at: string
  description: string
}

export interface Timetable {
  term: Term
  entries: Entry[]
  clashes: Clash[]
}

export type Priority = 'low' | 'normal' | 'high'

export interface Task {
  id: number
  title: string
  due_at: string
  course: string | null
  category: string | null
  origin: string
  done: boolean
  priority: Priority
  effort_minutes: number | null
  notes: string | null
  color: string | null
}

export interface TaskInput {
  title: string
  due_at: string
  course?: string | null
  category?: string | null
  priority?: Priority
  effort_minutes?: number | null
  notes?: string | null
}

export interface StudyBlock {
  task_id: number
  task_title: string
  day: string
  week: number
  starts_at: string
  ends_at: string
}

export interface Briefing {
  day: string
  term: Term
  now: string
  classes_today: Entry[]
  next_class: Entry | null
  classes_tomorrow: number
  due_soon: Task[]
  overdue: Task[]
  clashes: Clash[]
  unread_mail: number
  pending_approvals: number
  library_documents: number
  last_sync_at: string | null
  last_sync_outcome: string | null
  tips: string[]
}

export interface Academics {
  gpa: number | null
  rank: string | null
  credits_total: number | null
  credits_by_category: Record<string, number>
  credits_refreshed_at: string | null
  courses: { course: string, items: { item: string, score: string }[] }[]
}

export interface Material {
  id: number
  course_title: string
  section: string | null
  title: string
  url: string
}

export interface SyncRun {
  id: number
  trigger: string
  outcome: 'ok' | 'partial' | 'failed' | 'running'
  started_at: string
  finished_at: string | null
  steps: { source: string, ok: boolean, message: string }[]
}

export interface MailAccount {
  connected: boolean
  provider: string | null
  address: string | null
  linked_at: string | null
  last_synced_at: string | null
  providers: string[]
}

export interface MailSummary {
  id: number
  folder: string
  subject: string | null
  sender: string | null
  received_at: string | null
  preview: string | null
  seen: boolean
  has_attachments: boolean
}

export interface MailDetail extends MailSummary {
  recipients: string | null
  cc: string | null
  body_text: string | null
  body_html: string | null
}

export interface TaskCandidate {
  title: string
  due_at: string
  category: string | null
  notes: string | null
}

export type AskMode = 'agent' | 'ask' | 'research'

export interface Source {
  index: number
  kind: 'library' | 'web' | 'attachment'
  title: string
  excerpt: string
  url: string | null
}

export interface Step {
  id: string
  tool: string
  label: string
  status: 'running' | 'done' | 'failed'
  detail: string
}

export interface Turn {
  id: string
  mode: AskMode
  question: string
  answer: string
  reasoning: string | null
  sources: Source[]
  suggestions: string[]
  trace: Step[]
  failed: boolean
  created_at: string
}

export interface ConversationSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
  turn_count: number
}

export interface Attachment {
  id: number
  filename: string
  media_type: string
  size_bytes: number
  truncated: boolean
  created_at: string
}

export type ApprovalStatus = 'pending' | 'running' | 'done' | 'failed' | 'rejected' | 'expired'

export interface Approval {
  id: string
  conversation_id?: string | null
  kind: string
  title: string
  summary: string
  preview: string | null
  status: ApprovalStatus
  outcome?: string | null
  created_at?: string
  expires_at: string
}

export interface ConversationDetail {
  conversation: ConversationSummary
  turns: Turn[]
  attachments: Attachment[]
  approvals: Approval[]
}

export interface LibraryDocument {
  id: number
  filename: string
  media_type: string
  size_bytes: number
  chunks: number
  status: 'processing' | 'ready' | 'empty' | 'failed'
  error: string | null
  created_at: string
}

export interface LibraryState {
  available: boolean
  reason: string | null
  documents: LibraryDocument[]
}

export interface WorkspaceFile {
  path: string
  is_dir: boolean
  size: number
  modified: string
}

export interface WorkspaceListing {
  files: WorkspaceFile[]
  usage_bytes: number
  quota_bytes: number
}
