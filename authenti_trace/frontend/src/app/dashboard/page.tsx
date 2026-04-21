'use client'

import { useEffect, useState } from 'react'
import { apiUrl } from '@/lib/api'

interface Metrics {
  total_verifications: number;
  risk_distribution: {
    LOW_RISK: number;
    MEDIUM_RISK: number;
    HIGH_RISK: number;
  }
}

interface Audit {
  ledger_intact: boolean;
  chain_length: number;
  errors: string[];
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [audit, setAudit] = useState<Audit | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchData = async () => {
    setLoading(true)
    setError('')
    try {
      const [metricsResult, auditResult] = await Promise.allSettled([
        fetch(apiUrl('/api/v1/dashboard/metrics')),
        fetch(apiUrl('/api/v1/dashboard/audit'))
      ])

      const errors: string[] = []

      if (metricsResult.status === 'fulfilled' && metricsResult.value.ok) {
        setMetrics(await metricsResult.value.json())
      } else {
        errors.push('Metrics endpoint unavailable')
      }

      if (auditResult.status === 'fulfilled' && auditResult.value.ok) {
        setAudit(await auditResult.value.json())
      } else {
        errors.push('Audit endpoint unavailable')
      }

      if (errors.length > 0) {
        setError(errors.join(' | '))
      }
    } catch (e) {
      console.error("Dashboard fetch error", e)
      setError('Failed to load dashboard data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  if (loading && !metrics) {
    return (
      <main id="main-content" className="page page-dashboard">
        <div className="spinner dashboard-loader"></div>
      </main>
    )
  }

  const total = metrics?.total_verifications || 0
  const lowCount = metrics?.risk_distribution.LOW_RISK || 0
  const mediumCount = metrics?.risk_distribution.MEDIUM_RISK || 0
  const highCount = metrics?.risk_distribution.HIGH_RISK || 0
  const progressMax = total > 0 ? total : 1

  return (
    <main id="main-content" className="page page-dashboard">
      <section className="dashboard-header-row">
        <div>
          <p className="eyebrow">System Monitoring</p>
          <h1 className="page-title">System Monitoring Dashboard</h1>
        </div>
        <button className="btn btn-secondary" onClick={fetchData} type="button">Refresh</button>
      </section>

      {error && (
        <div className="card-soft dashboard-error" role="status">
          {error}
        </div>
      )}

      <section className="dashboard-stats-grid">
        <article className="card-soft stat-card">
          <h3>Total API Extractions</h3>
          <div className="stat-value">
            {total}
          </div>
        </article>

        <article className="card-soft stat-card">
          <h3>Cryptographic Ledger Status</h3>
          <div className="ledger-status-row">
            {audit?.ledger_intact ? (
              <>
                <span className="ledger-dot ledger-dot-safe" aria-hidden="true" />
                <span className="ledger-status-text">SECURE</span>
              </>
            ) : (
              <>
                <span className="ledger-dot ledger-dot-alert" aria-hidden="true" />
                <span className="ledger-status-text ledger-status-alert">TAMPER DETECTED</span>
              </>
            )}
          </div>
          <p className="ledger-chain-text">
            {audit?.chain_length} cryptographic blocks tracked.
          </p>
          {audit?.errors && audit.errors.length > 0 && (
             <div className="ledger-error-box">
                {audit.errors[0]}
             </div>
          )}
        </article>
      </section>

      <section className="card-soft distribution-card">
        <h2>Enforcement Risk Distribution</h2>
        <div className="risk-stack">
          <div>
            <div className="risk-row-head">
              <span className="badge-low status-badge">LOW RISK</span>
              <span>{lowCount} Queries</span>
            </div>
            <progress className="risk-track-progress risk-progress-low" value={lowCount} max={progressMax} aria-label="Low risk distribution" />
          </div>

          <div>
            <div className="risk-row-head">
              <span className="badge-medium status-badge">MEDIUM RISK</span>
              <span>{mediumCount} Queries</span>
            </div>
            <progress className="risk-track-progress risk-progress-medium" value={mediumCount} max={progressMax} aria-label="Medium risk distribution" />
          </div>

          <div>
            <div className="risk-row-head">
              <span className="badge-high status-badge">HIGH RISK</span>
              <span>{highCount} Queries</span>
            </div>
            <progress className="risk-track-progress risk-progress-high" value={highCount} max={progressMax} aria-label="High risk distribution" />
          </div>
        </div>
      </section>
    </main>
  )
}
