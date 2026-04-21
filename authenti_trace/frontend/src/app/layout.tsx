import './globals.css'
import Link from 'next/link'
import { ReactNode } from 'react'
import type { Metadata } from 'next'
import { Fraunces, Manrope } from 'next/font/google'

const displayFont = Fraunces({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['500', '600', '700'],
})

const bodyFont = Manrope({
  subsets: ['latin'],
  variable: '--font-body',
  weight: ['400', '500', '600', '700'],
})

export const metadata: Metadata = {
  title: 'AuthentiTrace',
  description: 'Multi-Signal Media Trust Infrastructure',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className={`${displayFont.variable} ${bodyFont.variable}`}>
        <a href="#main-content" className="skip-link">Skip to main content</a>

        <div className="site-backdrop" aria-hidden="true">
          <span className="site-glow site-glow-one" />
          <span className="site-glow site-glow-two" />
        </div>

        <header className="site-header">
          <div className="site-header-inner">
            <Link href="/" className="brand-mark" aria-label="AuthentiTrace home">
              <span className="brand-dot" aria-hidden="true" />
              <span>AuthentiTrace</span>
            </Link>

            <nav className="site-nav" aria-label="Primary">
              <Link href="/upload" className="site-nav-link">Verify Media</Link>
              <Link href="/dashboard" className="site-nav-link">Dashboard</Link>
            </nav>
          </div>
        </header>

        {children}
      </body>
    </html>
  )
}
