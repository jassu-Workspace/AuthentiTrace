import Link from 'next/link'

const signalHighlights = [
  {
    title: 'Content Signal',
    detail: 'Frequency-domain anomaly checks for synthetic generation artifacts.',
  },
  {
    title: 'Reality Signal',
    detail: 'Metadata and provenance posture analysis including C2PA confidence.',
  },
  {
    title: 'Behavioral Signal',
    detail: 'Motion and audio-visual coherence analysis for biometric plausibility.',
  },
  {
    title: 'Network Signal',
    detail: 'Propagation footprint scoring against OSINT disinformation patterns.',
  },
  {
    title: 'Integrity Signal',
    detail: 'Direct SHA-256 re-verification and malicious hash registry checks.',
  },
]

const platformPillars = [
  {
    title: 'Explainable Decisioning',
    detail: 'Every trust score ships with telemetry, confidence, and reasoning context.',
  },
  {
    title: 'Tamper-Evident Ledger',
    detail: 'Reports are chained with deterministic hashing for post-fact auditability.',
  },
  {
    title: 'Operational Readiness',
    detail: 'Upload, report, and dashboard flows built for analyst-facing verification loops.',
  },
]

export default function Home() {
  return (
    <main id="main-content" className="page page-home">
      <section className="hero-grid">
        <div className="hero-copy card-soft">
          <p className="eyebrow">Forensic Media Confidence Platform</p>
          <h1 className="hero-title">Tamper-Evident Media Trust</h1>
          <p className="hero-summary">
            AuthentiTrace is an enterprise-grade Multi-Signal Infrastructure.
            We cryptographically link behavioral, content, and network intelligence to guarantee the authenticity of digital media.
          </p>

          <div className="hero-actions">
            <Link href="/upload" className="btn btn-primary">Begin Verification</Link>
            <Link href="/dashboard" className="btn btn-secondary">View Dashboard</Link>
          </div>

          <div className="hero-metrics" aria-label="Platform highlights">
            <div className="hero-metric-item">
              <span className="hero-metric-label">Signals</span>
              <strong>5 Concurrent Engines</strong>
            </div>
            <div className="hero-metric-item">
              <span className="hero-metric-label">Ledger</span>
              <strong>SHA-256 Chained</strong>
            </div>
            <div className="hero-metric-item">
              <span className="hero-metric-label">Outcome</span>
              <strong>Explainable Trust Score</strong>
            </div>
          </div>
        </div>

        <aside className="hero-signals card-soft" aria-label="Signal stack overview">
          <h2>Signal Matrix</h2>
          <div className="signal-stack">
            {signalHighlights.map((signal) => (
              <article key={signal.title} className="signal-card">
                <h3>{signal.title}</h3>
                <p>{signal.detail}</p>
              </article>
            ))}
          </div>
        </aside>
      </section>

      <section className="value-grid" aria-label="Platform value pillars">
        {platformPillars.map((pillar) => (
          <article key={pillar.title} className="value-card card-soft">
            <h3>{pillar.title}</h3>
            <p>{pillar.detail}</p>
          </article>
        ))}
      </section>
    </main>
  )
}
