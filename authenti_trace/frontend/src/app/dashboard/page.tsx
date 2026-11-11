'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { apiRequest } from '@/lib/api'
import type { Audit, Metrics, Quality } from '@/lib/types'

const DRIFT_COPY: Record<Quality['drift']['status'], string> = {
  stable: 'Stable: recent scores look like the weeks before.',
  watch: 'Watch: recent scores have shifted a little.',
  alert: 'Alert: recent scores have shifted a lot. Check for new kinds of media or a changed model.',
  insufficient_data: 'Not enough recent data to compare.',
}

function pct(value: number | null | undefined): string {
  return value === null || value === undefined ? 'not measured' : `${(value * 100).toFixed(1)}%`
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [audit, setAudit] = useState<Audit | null>(null)
  const [quality, setQuality] = useState<Quality | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError('')
    const [m, a, q] = await Promise.allSettled([
      apiRequest<Metrics>('/api/v1/dashboard/metrics'),
      apiRequest<Audit>('/api/v1/dashboard/audit'),
      apiRequest<Quality>('/api/v1/dashboard/quality'),
    ])
    const problems: string[] = []
    if (m.status === 'fulfilled') setMetrics(m.value); else problems.push('Metrics')
    if (a.status === 'fulfilled') setAudit(a.value); else problems.push('Ledger audit')
    if (q.status === 'fulfilled') setQuality(q.value); else problems.push('Quality')
    if (problems.length) setError(`${problems.join(', ')} could not be loaded.`)
    setLoading(false)
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data load
    fetchData()
  }, [fetchData])

  if (loading && !metrics) {
    return (
      <main id="main-content" className="page page-dashboard">
        <p role="status" className="hud-stream-caption">Loading the dashboard…</p>
      </main>
    )
  }

  const total = metrics?.total_verifications ?? 0
  const dist = metrics?.risk_distribution
  const rows: { key: string; label: string; badge: string; value: number }[] = [
    { key: 'low', label: 'LOW RISK', badge: 'badge-low', value: dist?.LOW_RISK ?? 0 },
    { key: 'medium', label: 'MEDIUM RISK', badge: 'badge-medium', value: dist?.MEDIUM_RISK ?? 0 },
    { key: 'high', label: 'HIGH RISK', badge: 'badge-high', value: dist?.HIGH_RISK ?? 0 },
    { key: 'unknown', label: 'NEEDS REVIEW', badge: 'badge-review', value: dist?.UNKNOWN ?? 0 },
  ]
  const progressMax = total > 0 ? total : 1
  const histMax = Math.max(1, ...(quality?.score_distribution ?? [0]))

  return (
    <main id="main-content" className="page page-dashboard">
      <section className="dashboard-header-row animate-slide-down">
        <div>
          <p className="eyebrow">Operations</p>
          <h1 className="page-title">System dashboard</h1>
        </div>
        <button className="btn btn-secondary" onClick={fetchData} type="button" disabled={loading}>
          {loading && <span className="spinner-sm" aria-hidden="true" />}
          Refresh
        </button>
      </section>

      {error && <div className="card-soft dashboard-error" role="alert">{error}</div>}

      <section className="dashboard-stats-grid animate-scale-in">
        <article className="card-soft stat-card">
          <h2 className="stat-title">Verifications</h2>
          <div className="stat-value">{total}</div>
        </article>

        <article className="card-soft stat-card">
          <h2 className="stat-title">Ledger</h2>
          <div className="ledger-status-row">
            {audit?.ledger_intact ? (
              <>
                <span className="ledger-dot ledger-dot-safe" aria-hidden="true" />
                <span className="ledger-status-text">INTACT</span>
              </>
            ) : (
              <>
                <span className="ledger-dot ledger-dot-alert" aria-hidden="true" />
                <span className="ledger-status-text ledger-status-alert">{audit ? 'PROBLEM FOUND' : 'UNKNOWN'}</span>
              </>
            )}
          </div>
          <p className="ledger-chain-text">
            {audit?.chain_length ?? 0} records checked
            {audit?.anchor_head_seq != null ? `; anchor at #${audit.anchor_head_seq}` : '; no anchor file'}.
          </p>
          {audit && audit.errors.length > 0 && (
            <div className="ledger-error-box">
              {audit.errors[0]}
              {audit.errors_total > 1 ? ` (and ${audit.errors_total - 1} more)` : ''}
            </div>
          )}
        </article>

        <article className="card-soft stat-card">
          <h2 className="stat-title">Waiting for review</h2>
          <div className="stat-value">{quality?.review_backlog ?? 0}</div>
          <Link href="/review">Open the review queue</Link>
        </article>
      </section>

      <section className="card-soft distribution-card animate-scale-in">
        <h2>Verdicts</h2>
        <div className="risk-stack">
          {rows.map((r) => (
            <div key={r.key}>
              <div className="risk-row-head">
                <span className={`${r.badge} status-badge`}>{r.label}</span>
                <span>{r.value}</span>
              </div>
              <progress className={`risk-track-progress risk-progress-${r.key}`} value={r.value} max={progressMax} aria-label={`${r.label}: ${r.value} of ${total}`} />
            </div>
          ))}
        </div>
      </section>

      <section className="card-soft distribution-card">
        <h2>Scores in the last {quality?.drift.window_days ?? 7} days</h2>
        <div className="hist" role="img" aria-label={`Score histogram of ${quality?.recent_count ?? 0} recent verifications`}>
          {(quality?.score_distribution ?? []).map((count, i) => (
            <div key={i} className="hist-col">
              <div className="hist-bar" style={{ height: `${(count / histMax) * 100}%` }} title={`${i * 10}-${i * 10 + 10}: ${count}`} />
              <span className="hist-label">{i * 10}</span>
            </div>
          ))}
        </div>
        <p className={`drift-note drift-${quality?.drift.status ?? 'insufficient_data'}`}>
          {DRIFT_COPY[quality?.drift.status ?? 'insufficient_data']}
          {quality?.drift.psi != null ? ` (PSI ${quality.drift.psi})` : ''}
        </p>
      </section>

      <section className="card-soft distribution-card">
        <h2>Accuracy on labeled files</h2>
        {quality?.latest_eval ? (
          <>
            <table className="eval-table">
              <tbody>
                <tr><th scope="row">Fakes approved by mistake</th><td>{pct(quality.latest_eval.false_approval_rate)}</td></tr>
                <tr><th scope="row">Real files flagged</th><td>{pct(quality.latest_eval.false_alarm_rate)}</td></tr>
                <tr><th scope="row">Sent to review</th><td>{pct(quality.latest_eval.unsure_rate)}</td></tr>
                <tr><th scope="row">Files measured</th><td>{quality.latest_eval.n} ({quality.latest_eval.split})</td></tr>
              </tbody>
            </table>
            <p className="report-note">Measured {new Date(quality.latest_eval.evaluated_at * 1000).toLocaleDateString()}.</p>
          </>
        ) : (
          <p>
            Not measured yet. Run the evaluation on labeled files and save the result as
            <code> backend/eval/results/latest.json</code> to show accuracy here.
          </p>
        )}
      </section>
    </main>
  )
}
