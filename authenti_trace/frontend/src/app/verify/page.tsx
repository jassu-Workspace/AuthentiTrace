'use client'

import { FormEvent, Suspense, useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { apiRequest, errorMessage } from '@/lib/api'
import { formatDate, verdictCopy } from '@/lib/explain'
import type { Proof, Report } from '@/lib/types'

const HASH_RE = /^[0-9a-fA-F]{64}$/

function Step({ ok, title, detail }: { ok: boolean; title: string; detail: string }) {
  return (
    <li className={`proof-step ${ok ? 'proof-ok' : 'proof-bad'}`}>
      <span className="proof-mark" aria-hidden="true">{ok ? '✓' : '✗'}</span>
      <div>
        <strong>{title}</strong>
        <p>{detail}</p>
      </div>
      <span className="sr-only">{ok ? 'Passed' : 'Failed'}</span>
    </li>
  )
}

const ANCHOR_COPY: Record<Proof['anchored'], { ok: boolean; text: string }> = {
  yes: { ok: true, text: 'The hash was also written to the anchor file, outside the database, and they match.' },
  not_anchored: { ok: true, text: 'This record is older than the anchor file, so it cannot be compared with it.' },
  no_anchor_file: { ok: true, text: 'No anchor file exists on this server, so deleted records cannot be detected.' },
  mismatch: { ok: false, text: 'The anchor file holds a different hash for this record. The database was changed.' },
}

function VerifyInner() {
  const params = useSearchParams()
  const initial = params.get('id') ?? ''
  const [query, setQuery] = useState(initial)
  const [proof, setProof] = useState<Proof | null>(null)
  const [matches, setMatches] = useState<Report[] | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const run = useCallback(async (raw: string) => {
    const q = raw.trim()
    setError('')
    setProof(null)
    setMatches(null)
    if (!q) return
    setBusy(true)
    try {
      if (HASH_RE.test(q)) {
        setMatches(await apiRequest<Report[]>(`/api/v1/reports/by-hash/${q.toLowerCase()}`))
      } else {
        setProof(await apiRequest<Proof>(`/api/v1/reports/${encodeURIComponent(q)}/proof`))
      }
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    if (initial) {
      run(initial)
    }
  }, [initial, run])

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    run(query)
  }

  return (
    <main id="main-content" className="page page-verify">
      <section className="upload-intro">
        <p className="eyebrow">Independent check</p>
        <h1 className="page-title">Verify a record</h1>
        <p className="upload-description">
          Paste a record id to check that it is an unbroken part of the ledger, or paste a file SHA-256 to find every
          record for that file.
        </p>
      </section>

      <form className="card-soft verify-form" onSubmit={onSubmit}>
        <label htmlFor="verify-query">Record id or file SHA-256</label>
        <input
          id="verify-query"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoComplete="off"
          spellCheck={false}
        />
        <button className="btn btn-primary" type="submit" disabled={busy || !query.trim()}>
          {busy ? 'Checking…' : 'Check'}
        </button>
      </form>

      {error && <div className="card-soft dashboard-error" role="alert">{error}</div>}

      {proof && (
        <section className="card-soft" aria-live="polite">
          <h2 className="report-card-title">
            {proof.verified ? 'This record checks out' : 'This record failed a check'}
          </h2>
          <p>Record #{proof.seq} · chain length {proof.chain_head_seq} · <Link href={`/report/${proof.id}`}>open the report</Link></p>
          <ul className="proof-list">
            <Step
              ok={proof.hash_valid}
              title="The record matches its hash"
              detail={proof.hash_valid ? 'Recomputing the hash from the stored data gives the stored hash.' : 'The stored data no longer produces the stored hash. The record was changed.'}
            />
            <Step
              ok={proof.links_to_previous}
              title="It links to the previous record"
              detail={proof.links_to_previous ? 'The previous record’s hash matches the link stored here.' : 'The previous record is missing or different. The chain is broken here.'}
            />
            <Step ok={ANCHOR_COPY[proof.anchored].ok} title="Anchored outside the database" detail={ANCHOR_COPY[proof.anchored].text} />
          </ul>
          {proof.review_of && (
            <p>This record is a reviewer’s decision about <Link href={`/report/${proof.review_of}`}>an earlier verdict</Link>.</p>
          )}
        </section>
      )}

      {matches && (
        <section className="card-soft">
          <h2 className="report-card-title">{matches.length} record{matches.length === 1 ? '' : 's'} for this file</h2>
          <ul className="match-list">
            {matches.map((m) => (
              <li key={m.id}>
                <Link href={`/verify?id=${encodeURIComponent(m.id)}`}>#{m.seq}</Link>
                {' · '}{verdictCopy(m.enforcement_action).headline}{' · '}{formatDate(m.created_at)}
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  )
}

export default function VerifyPage() {
  return (
    <Suspense fallback={<main id="main-content" className="page"><p role="status">Loading…</p></main>}>
      <VerifyInner />
    </Suspense>
  )
}
