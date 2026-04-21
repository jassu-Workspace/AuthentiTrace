'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { apiUrl } from '@/lib/api'

interface Telemetry {
  [key: string]: {
    plugin_name: string;
    score: number;
    confidence: number;
    reasoning: string;
    metadata: unknown;
  }
}

interface Report {
  id: string;
  media_reference_id: string;
  file_hash: string;
  composite_score: number;
  risk_category: string;
  enforcement_action: string;
  previous_hash: string;
  current_hash: string;
  created_at: string;
  signal_telemetry: Telemetry;
}

export default function ReportPage() {
  const { id } = useParams()
  const reportId = Array.isArray(id) ? id[0] : id
  const [report, setReport] = useState<Report | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!reportId) {
      return
    }

    fetch(apiUrl(`/api/v1/reports/${reportId}`))
      .then(res => {
        if (!res.ok) throw new Error('Report not found')
        return res.json()
      })
      .then(data => {
        setReport(data)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [reportId])

  if (!reportId) {
    return (
      <main id="main-content" className="page page-report">
        <div className="card-soft report-inline-message">
          <p className="report-error-text">Invalid report id</p>
        </div>
      </main>
    )
  }

  if (loading) {
    return (
      <main id="main-content" className="page page-report">
        <div className="spinner report-loader"></div>
      </main>
    )
  }

  if (error || !report) {
    return (
      <main id="main-content" className="page page-report">
        <div className="card-soft report-inline-message">
          <p className="report-error-text">{error}</p>
        </div>
      </main>
    )
  }

  const getBadgeClass = (risk: string) => {
    if (risk === 'LOW_RISK') return 'badge-low'
    if (risk === 'MEDIUM_RISK') return 'badge-medium'
    return 'badge-high'
  }

  const scoreToneClass = report.composite_score >= 75 ? 'score-positive' : report.composite_score >= 40 ? 'score-warning' : 'score-danger'

  return (
    <main id="main-content" className="page page-report">
      <div className="report-header-row">
        <h1 className="page-title">Trust Report</h1>
        <span className={`status-badge report-risk-badge ${getBadgeClass(report.risk_category)}`}>
          {report.risk_category.replace('_', ' ')}
        </span>
      </div>

      <div className="report-layout-grid">
        <div className="report-left-column">
          <section className="card-soft report-score-card">
            <h3>Weighted Trust Score</h3>
            <div className={`report-score-number ${scoreToneClass}`}>
              {Math.round(report.composite_score)}
            </div>
            <p>OUT OF 100</p>
          </section>

          <section className="card-soft report-ledger-card">
            <h3>Ledger Receipt</h3>
            <div className="ledger-detail-stack">
              <div className="ledger-detail-row">
                <span>Media GUID</span>
                <code>{report.media_reference_id}</code>
              </div>
              <div className="ledger-detail-row">
                <span>Computed SHA-256</span>
                <code>{report.file_hash}</code>
              </div>
              <div className="ledger-detail-row">
                <span>Cryptographic Block Hash</span>
                <code>{report.current_hash}</code>
              </div>
            </div>
          </section>
        </div>

        <section className="card-soft report-telemetry-card">
          <h3>Signal Telemetry Breakdown</h3>
          <p>The engine dynamically queries and aggregates independent micro-services modeling distinct reality vectors.</p>

          {Object.values(report.signal_telemetry).map((sig, i) => (
            <article key={i} className="telemetry-row">
              <div className="telemetry-row-header">
                <strong>{sig.plugin_name}</strong>
                <span className="telemetry-score-chip">
                  Score: <strong className={sig.score > 50 ? 'score-positive' : 'score-danger'}>{sig.score.toFixed(1)}</strong>
                </span>
              </div>
              <p className="telemetry-reasoning">{sig.reasoning}</p>
              <div className="telemetry-row-foot">
                <span>Confidence: {(sig.confidence * 100).toFixed(0)}%</span>
                <span>Runtime Metadata Available</span>
              </div>
            </article>
          ))}
        </section>
      </div>
    </main>
  )
}
