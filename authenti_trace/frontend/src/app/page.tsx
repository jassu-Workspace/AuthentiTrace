import Link from 'next/link'

const signalHighlights = [
  {
    title: 'Content Signal',
    detail: '2D FFT spectral lattice ratio, ELA compression divergence, and silicon PRNU sensor noise residuals.',
  },
  {
    title: 'Reality Signal',
    detail: 'C2PA cryptographic JUMBF provenance, camera hardware EXIF, and Bayer CFA demosaicing peaks.',
  },
  {
    title: 'Behavioral Signal',
    detail: 'Directional illuminant vector consistency, optical focus gradients, and video rPPG biological pulse waves.',
  },
  {
    title: 'Network Signal',
    detail: '64-bit difference perceptual hashing (dHash) and deduplication against synthetic registries.',
  },
  {
    title: 'Integrity Signal',
    detail: 'Direct streaming SHA-256 byte-by-byte verification and malicious hash registry lookup.',
  },
]

const platformPillars = [
  {
    title: 'Physical Invariant Forensics',
    detail: 'Detection grounded in hardware silicon, optics, and biological circulation that AI cannot manufacture.',
  },
  {
    title: 'Tamper-Evident Ledger',
    detail: 'Every verdict is cryptographically hashed and chained sequentially for court-admissible auditability.',
  },
  {
    title: 'Operational Readiness',
    detail: 'Upload, interactive forensic inspection, and real-time ledger audit tools built for analysts.',
  },
]

export default function Home() {
  return (
    <main id="main-content" className="page page-home">
      <section className="hero-grid animate-slide-down">
        <div className="hero-copy card-soft">
          <p className="eyebrow">Forensic Media Confidence Platform</p>
          <h1 className="hero-title">Tamper-Evident Media Trust</h1>
          <p className="hero-summary">
            AuthentiTrace is an enterprise-grade Multi-Signal Infrastructure.
            We cryptographically link physical invariants, camera hardware provenance, and network intelligence to guarantee the authenticity of digital media in real time.
          </p>

          <div className="hero-actions">
            <Link href="/upload" className="btn btn-primary">Begin Verification</Link>
            <Link href="/dashboard" className="btn btn-secondary">View Dashboard</Link>
          </div>

          <div className="hero-metrics" aria-label="Platform highlights">
            <div className="hero-metric-item">
              <span className="hero-metric-label">Signals</span>
              <strong>5 Concurrent Invariant Engines</strong>
            </div>
            <div className="hero-metric-item">
              <span className="hero-metric-label">Ledger</span>
              <strong>SHA-256 Chained</strong>
            </div>
            <div className="hero-metric-item">
              <span className="hero-metric-label">Outcome</span>
              <strong>Court-Grade Forensic Telemetry</strong>
            </div>
          </div>
        </div>

        <aside className="hero-signals card-soft animate-scale-in" aria-label="Signal stack overview">
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

      <section className="value-grid animate-scale-in" aria-label="Platform value pillars">
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
