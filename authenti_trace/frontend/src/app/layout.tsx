import './globals.css'
import { ReactNode } from 'react'
import type { Metadata } from 'next'
import { Fraunces, Manrope } from 'next/font/google'
import { SiteHeader } from '@/components/SiteHeader'

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

        <SiteHeader />

        {children}
      </body>
    </html>
  )
}
