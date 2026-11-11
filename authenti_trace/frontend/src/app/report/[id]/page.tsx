'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { apiRequest, errorMessage } from '@/lib/api'
import { confidenceLabel, formatDate, signalLabel, verdictCopy } from '@/lib/explain'
import { decisionOf, reviewOf, signalsOf } from '@/lib/types'
import type { Report, SignalItem } from '@/lib/types'

function toneClass(tone: string): string {
  return tone === 'good' ? 'badge-low' : tone === 'warn' ? 'badge-medium' : tone === 'bad' ? 'badge-high' : 'badge-review'
}

function scoreTone(score: number, abstained: boolean): string {
  if (abstained) return 'score-warning'
  return score >= 75 ? 'score-positive' : score >= 40 ? 'score-warning' : 'score-danger'
}

/** Short facts from a signal's metadata, in plain words. Only shows what the metadata really says. */
function facts(sig: SignalItem): string[] {
  const m = (sig.metadata ?? {}) as Record<string, unknown>
  const out: string[] = []
  if (m.c2pa_verified === true) out.push('Signed Content Credentials: verified')
  else if (m.c2pa_detected === true) out.push('Content Credentials markers found, but not verified')
  if (typeof m.camera_make === 'string' && typeof m.camera_model === 'string') {
    out.push(`Camera metadata: ${m.camera_make} ${m.camera_model} (can be forged)`)
  }
  if (typeof m.software_signature === 'string') out.push(`Software tag: ${m.software_signature}`)
  if (typeof m.ela_mean === 'number') out.push(`Compression difference: ${m.ela_mean}`)
  if (typeof m.focus_variance === 'number') out.push(`Focus detail: ${m.focus_variance}`)
  if (typeof m.detected_bpm === 'number' && m.detected_bpm > 0) out.push(`Pulse-like signal: ${m.detected_bpm} BPM`)
  if (m.registry_loaded === false) out.push('No reference list is loaded, so nothing was compared')
  else if (m.registry_hit === true || m.blacklist_hit === true) out.push('Matched a known bad entry')
  else if (m.registry_loaded === true) out.push('No match in the reference list')
  if (typeof m.p_real === 'number') out.push(`Model probability real: ${(m.p_real * 100).toFixed(0)}%`)
  return out
}

export default function ReportPage() {
  const { id } = useParams()
  const reportId = Array.isArray(id) ? id[0] : id
  const [report, setReport] = useState<Report | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!reportId) return
    let active = true
    apiRequest<Report>(`/api/v1/reports/${encodeURIComponent(reportId)}`)
      .then((data) => active && setReport(data))
      .catch((err) => active && setError(errorMessage(err)))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [reportId])

  const handleCopyReceipt = async () => {
    if (!report) return
    const receipt = {
      report_id: report.id,
      seq: report.seq,
      media_guid: report.media_reference_id,
      sha256: report.file_hash,
      ledger_block_hash: report.current_hash,
      previous_hash: report.previous_hash,
      score: report.composite_score,
      action: report.enforcement_action,
      created_at: report.created_at,
    }
    try {
      await navigator.clipboard.writeText(JSON.stringify(receipt, null, 2))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError('Copying is not allowed in this browser.')
    }
  }

  if (!reportId) {
    return (
      <main id="main-content" className="page page-report">
        <div className="card-soft report-inline-message">
          <p className="report-error-text">Invalid report id.</p>
        </div>
      </main>
    )
  }

  if (loading) {
    return (
      <main id="main-content" className="page page-report">
        <p role="status" className="hud-stream-caption">Loading the report…</p>
      </main>
    )
  }

  if (!report) {
    return (
      <main id="main-content" className="page page-report">
        <div className="card-soft report-inline-message" role="alert">
          <p className="report-error-text">{error || 'Report not found.'}</p>
          <div style={{ marginTop: '1rem' }}>
            <Link href="/upload" className="btn btn-secondary btn-back-link">← Verify another file</Link>
          </div>
        </div>
      </main>
    )
  }

  const verdict = verdictCopy(report.enforcement_action)
  const decision = decisionOf(report.signal_telemetry)
  const review = reviewOf(report.signal_telemetry)
  const signals = signalsOf(report.signal_telemetry)
  const abstained = report.enforcement_action === 'MANUAL_REVIEW'
  const score = report.composite_score ?? 0
  const needsReview = report.enforcement_action === 'MANUAL_REVIEW' || report.enforcement_action === 'FLAG'

  return (
    <main id="main-content" className="page page-report">
      <div className="report-header-row animate-slide-down">
        <div>
          <p className="eyebrow">Verification result</p>
          <h1 className="page-title">{verdict.headline}</h1>
          <p className="report-verdict-detail">{verdict.detail}</p>
        </div>
        <div className="report-header-actions">
          <Link href="/upload" className="btn btn-secondary btn-back-link">← Verify another file</Link>
          <span className={`status-badge report-risk-badge ${toneClass(verdict.tone)}`}>
            {(report.enforcement_action ?? 'NONE').replace('_', ' ')}
          </span>
        </div>
      </div>

      {decision?.reason && (
        <p className="report-reason card-soft" role="note">
          <strong>Why:</strong> {decision.reason}
        </p>
      )}

      {review && (
        <p className="report-reason card-soft" role="note">
          <strong>Reviewer {review.reviewer}:</strong> {review.decision === 'approve' ? 'approved' : 'rejected'}
          {review.note ? ` — ${review.note}` : ''}. <Link href={`/report/${review.of}`}>See the original verdict</Link>.
        </p>
      )}

      <div className="report-layout-grid">
        <div className="report-left-column animate-scale-in">
          <section className="card-soft report-score-card">
            <h2 className="report-card-title">{decision?.calibrated ? 'Probability real' : 'Raw score (uncalibrated)'}</h2>
            <div className={`report-score-number ${scoreTone(score, abstained)}`} aria-label={`Score ${Math.round(score)} out of 100`}>
              {Math.round(score)}
            </div>
            <p>OUT OF 100</p>
            {!decision?.calibrated && (
              <p className="report-note">
                This score comes from rule-based checks and has not been measured against labeled data. Treat it as a
                rough guide.
              </p>
            )}
          </section>

          {needsReview && (
            <section className="card-soft">
              <h2 className="report-card-title">A person should decide</h2>
              <p>This verdict is waiting in the review queue.</p>
              <Link href="/review" className="btn btn-primary">Open the review queue</Link>
            </section>
          )}

          <section className="card-soft report-ledger-card">
            <h2 className="report-card-title">Ledger receipt</h2>
            <div className="ledger-detail-stack">
              <div className="ledger-detail-row"><span>Record</span><code>#{report.seq} · {report.id}</code></div>
              <div className="ledger-detail-row"><span>Recorded</span><code>{formatDate(report.created_at)}</code></div>
              <div className="ledger-detail-row"><span>File SHA-256</span><code>{report.file_hash}</code></div>
              <div className="ledger-detail-row"><span>Block hash</span><code>{report.current_hash}</code></div>
            </div>
            <div className="report-actions-row">
              <button onClick={handleCopyReceipt} type="button" className="btn btn-secondary btn-copy-receipt">
                {copied ? '✓ Receipt copied' : 'Copy receipt'}
              </button>
              <Link href={`/verify?id=${encodeURIComponent(report.id)}`} className="btn btn-secondary">
                Verify this record
              </Link>
            </div>
          </section>
        </div>

        <section className="card-soft report-telemetry-card animate-scale-in">
          <h2 className="report-card-title">What each check found</h2>
          <p>Each check is independent. A check with no evidence does not count towards the verdict.</p>

          {signals.length === 0 ? (
            <p className="report-empty-telemetry">No signal details are stored for this record.</p>
          ) : (
            signals.map((sig, i) => {
              const label = signalLabel(sig.plugin_name)
              const silent = sig.confidence <= 0
              const found = facts(sig)
              return (
                <article key={sig.plugin_name || i} className="telemetry-row animate-stagger-item" style={{ animationDelay: `${i * 60}ms` }}>
                  <div className="telemetry-row-header">
                    <strong>{label.title}</strong>
                    <span className="telemetry-score-chip">
                      {silent ? (
                        <span className="evidence-none">No evidence</span>
                      ) : (
                        <>Score <strong className={sig.score > 50 ? 'score-positive' : 'score-danger'}>{Number(sig.score).toFixed(0)}</strong></>
                      )}
                    </span>
                  </div>
                  <p className="telemetry-what">{label.what}</p>
                  <p className="telemetry-reasoning">{sig.reasoning}</p>

                  {found.length > 0 && (
                    <ul className="telemetry-facts">{found.map((f) => <li key={f}>{f}</li>)}</ul>
                  )}

                  <div className="telemetry-row-foot">
                    <span>{confidenceLabel(Number(sig.confidence || 0))} ({(Number(sig.confidence || 0) * 100).toFixed(0)}%)</span>
                    <meter className="confidence-meter" min={0} max={1} value={Number(sig.confidence || 0)} aria-label={`Confidence ${(Number(sig.confidence || 0) * 100).toFixed(0)} percent`} />
                  </div>

                  {sig.metadata && Object.keys(sig.metadata).length > 0 && (
                    <details className="telemetry-raw-details">
                      <summary className="telemetry-raw-summary">Technical details</summary>
                      <pre className="telemetry-raw-code">{JSON.stringify(sig.metadata, null, 2)}</pre>
                    </details>
                  )}
                </article>
              )
            })
          )}
        </section>
      </div>
    </main>
  )
}
