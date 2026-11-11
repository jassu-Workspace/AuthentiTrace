// Shapes returned by the backend. Keep in sync with backend/app/schemas/verification.py.

export interface SignalItem {
  plugin_name: string
  score: number
  confidence: number
  reasoning: string
  metadata?: Record<string, unknown>
}

export interface Decision {
  reason: string
  evidence: number
  calibrated: boolean
}

export interface ReviewNote {
  of: string
  decision: 'approve' | 'reject'
  note: string
  reviewer: string
}

// Telemetry holds one SignalItem per signal plus underscore keys ("_decision", "_review") that are not signals.
export type Telemetry = Record<string, unknown>

export interface Report {
  id: string
  seq: number
  hash_version: number
  versions: Record<string, unknown> | null
  media_reference_id: string
  file_hash: string
  composite_score: number | null
  risk_category: string | null
  enforcement_action: string | null
  signal_telemetry: Telemetry | null
  previous_hash: string
  current_hash: string
  created_at: string
}

export interface Job {
  job_id: string
  status: 'queued' | 'running' | 'done' | 'failed'
  attempts: number
  report_id: string | null
  error: string | null
}

export interface PendingReview {
  id: string
  seq: number
  media_reference_id: string
  composite_score: number | null
  risk_category: string | null
  enforcement_action: string | null
  reason: string
  created_at: string
}

export interface Proof {
  id: string
  seq: number
  hash_version: number
  current_hash: string
  previous_hash: string
  hash_valid: boolean
  links_to_previous: boolean
  anchored: 'yes' | 'no_anchor_file' | 'not_anchored' | 'mismatch'
  chain_head_seq: number
  verified: boolean
  review_of: string | null
}

export interface Metrics {
  total_verifications: number
  risk_distribution: { LOW_RISK: number; MEDIUM_RISK: number; HIGH_RISK: number; UNKNOWN: number }
}

export interface Audit {
  ledger_intact: boolean
  chain_length: number
  errors: string[]
  errors_total: number
  anchor_head_seq: number | null
}

export interface EvalSummary {
  n: number
  split: string | null
  false_approval_rate: number | null
  false_alarm_rate: number | null
  unsure_rate: number | null
  evaluated_at: number
}

export interface Quality {
  review_backlog: number
  score_distribution: number[]
  recent_count: number
  drift: { psi: number | null; status: 'stable' | 'watch' | 'alert' | 'insufficient_data'; window_days: number }
  latest_eval: EvalSummary | null
}

/** Signals only: drops the underscore keys and anything that does not look like a signal. */
export function signalsOf(telemetry: Telemetry | null): SignalItem[] {
  if (!telemetry || typeof telemetry !== 'object') return []
  return Object.entries(telemetry)
    .filter(([key, value]) => !key.startsWith('_') && typeof value === 'object' && value !== null)
    .map(([, value]) => value as SignalItem)
}

export function decisionOf(telemetry: Telemetry | null): Decision | null {
  const value = telemetry?._decision
  return value && typeof value === 'object' ? (value as Decision) : null
}

export function reviewOf(telemetry: Telemetry | null): ReviewNote | null {
  const value = telemetry?._review
  return value && typeof value === 'object' ? (value as ReviewNote) : null
}
