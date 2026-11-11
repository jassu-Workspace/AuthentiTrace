// Plain-language wording for verdicts and signals. No raw backend text is shown for errors.

export interface VerdictCopy {
  headline: string
  detail: string
  tone: 'good' | 'warn' | 'bad' | 'review'
}

export function verdictCopy(action: string | null): VerdictCopy {
  switch (action) {
    case 'APPROVE':
      return { headline: 'Likely authentic', detail: 'The checks that could run found nothing suspicious. This is a screening result, not proof.', tone: 'good' }
    case 'FLAG':
      return { headline: 'Needs a closer look', detail: 'Some checks found signs worth a second opinion. A person should review it.', tone: 'warn' }
    case 'RESTRICT':
      return { headline: 'Likely manipulated', detail: 'At least one strong check failed. Do not rely on this media until it is reviewed.', tone: 'bad' }
    case 'MANUAL_REVIEW':
      return { headline: 'The system cannot tell', detail: 'There was not enough evidence, or the checks disagreed. A person should decide.', tone: 'review' }
    case 'HUMAN_APPROVE':
      return { headline: 'Approved by a reviewer', detail: 'A person looked at the earlier verdict and approved it.', tone: 'good' }
    case 'HUMAN_REJECT':
      return { headline: 'Rejected by a reviewer', detail: 'A person looked at the earlier verdict and rejected the media.', tone: 'bad' }
    default:
      return { headline: 'No verdict', detail: 'This record has no verdict.', tone: 'review' }
  }
}

export const SIGNAL_LABELS: Record<string, { title: string; what: string }> = {
  ContentSignal: { title: 'Image structure', what: 'Looks at compression and noise patterns for signs of editing or splicing.' },
  RealitySignal: { title: 'Origin and metadata', what: 'Checks signed Content Credentials, camera data and generator names in the file.' },
  BehavioralSignal: { title: 'Focus and motion', what: 'Checks focus patterns in photos and a pulse-like signal in video.' },
  NetworkSignal: { title: 'Known fakes', what: 'Compares the image fingerprint with a list of known synthetic images.' },
  IntegritySignal: { title: 'Known bad files', what: 'Compares the file hash with a list of known malicious files.' },
  ModelSignal: { title: 'Trained detector', what: 'A machine-learning model estimates how likely the image is real.' },
}

export function signalLabel(name: string): { title: string; what: string } {
  return SIGNAL_LABELS[name] ?? { title: name, what: 'An additional check.' }
}

export function confidenceLabel(confidence: number): string {
  if (confidence <= 0) return 'No evidence'
  if (confidence < 0.4) return 'Weak evidence'
  if (confidence < 0.75) return 'Moderate evidence'
  return 'Strong evidence'
}

export const JOB_STATUS_COPY: Record<string, string> = {
  queued: 'Waiting for a worker…',
  running: 'Analyzing the file…',
  done: 'Finished. Opening the report…',
  failed: 'The analysis did not finish.',
}

export const JOB_ERROR_COPY: Record<string, string> = {
  VERIFICATION_FAILED: 'The analysis failed twice. Try again, or try a different file.',
  MEDIA_MISSING: 'The uploaded file is no longer available. Upload it again.',
}

export function formatDate(iso: string): string {
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}
