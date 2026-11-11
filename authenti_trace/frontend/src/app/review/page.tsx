'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { apiRequest, errorMessage } from '@/lib/api'
import { formatDate, verdictCopy } from '@/lib/explain'
import type { PendingReview } from '@/lib/types'

function ReviewItem({ item, onDone }: { item: PendingReview; onDone: (id: string) => void }) {
  const [note, setNote] = useState('')
  const [reviewer, setReviewer] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const verdict = verdictCopy(item.enforcement_action)

  const decide = async (decision: 'approve' | 'reject') => {
    setBusy(true)
    setError('')
    try {
      await apiRequest(`/api/v1/reviews/${encodeURIComponent(item.id)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, note, reviewer: reviewer.trim() || 'anonymous' }),
      })
      onDone(item.id)
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <li className="card-soft review-item">
      <div className="review-item-head">
        <div>
          <strong>{verdict.headline}</strong>
          <span className="review-meta"> · record #{item.seq} · {formatDate(item.created_at)}</span>
        </div>
        <span className="telemetry-score-chip">Score {Math.round(item.composite_score ?? 0)}</span>
      </div>
      {item.reason && <p className="review-reason">{item.reason}</p>}
      <p><Link href={`/report/${item.id}`}>Open the full report</Link></p>

      <div className="review-form">
        <label>
          <span>Your name</span>
          <input type="text" value={reviewer} maxLength={80} onChange={(e) => setReviewer(e.target.value)} placeholder="anonymous" />
        </label>
        <label>
          <span>Note (optional)</span>
          <textarea value={note} maxLength={500} rows={2} onChange={(e) => setNote(e.target.value)} />
        </label>
        <div className="review-buttons">
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => decide('approve')}>
            Approve as authentic
          </button>
          <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => decide('reject')}>
            Reject as manipulated
          </button>
        </div>
        {error && <p className="upload-error" role="alert">{error}</p>}
      </div>
    </li>
  )
}

export default function ReviewPage() {
  const [items, setItems] = useState<PendingReview[] | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      setItems(await apiRequest<PendingReview[]>('/api/v1/reviews/pending'))
    } catch (err) {
      setError(errorMessage(err))
      setItems([])
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data load
    load()
  }, [load])

  return (
    <main id="main-content" className="page page-review">
      <section className="dashboard-header-row">
        <div>
          <p className="eyebrow">Human review</p>
          <h1 className="page-title">Review queue</h1>
          <p className="upload-description">
            These verdicts need a person. Each decision is saved as a new ledger record. The original verdict is never
            changed.
          </p>
        </div>
        <button className="btn btn-secondary" type="button" onClick={load}>Refresh</button>
      </section>

      {error && <div className="card-soft dashboard-error" role="alert">{error}</div>}

      {items === null ? (
        <p role="status" className="hud-stream-caption">Loading the queue…</p>
      ) : items.length === 0 && !error ? (
        <p className="card-soft" role="status">Nothing is waiting for review.</p>
      ) : (
        <ul className="review-list">
          {items.map((item) => (
            <ReviewItem key={item.id} item={item} onDone={(id) => setItems((cur) => (cur ?? []).filter((i) => i.id !== id))} />
          ))}
        </ul>
      )}
    </main>
  )
}
