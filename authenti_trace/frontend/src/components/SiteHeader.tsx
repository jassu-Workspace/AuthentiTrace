'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const LINKS = [
  { href: '/upload', label: 'Verify Media' },
  { href: '/review', label: 'Review' },
  { href: '/verify', label: 'Verify a Record' },
  { href: '/dashboard', label: 'Dashboard' },
]

export function SiteHeader() {
  const pathname = usePathname()

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Link href="/" className="brand-mark" aria-label="AuthentiTrace home">
          <span className="brand-dot" aria-hidden="true" />
          <span>AuthentiTrace</span>
        </Link>

        <nav className="site-nav" aria-label="Primary">
          {LINKS.map(({ href, label }) => {
            const active = pathname === href
            return (
              <Link
                key={href}
                href={href}
                className={`site-nav-link ${active ? 'site-nav-link-active' : ''}`}
                aria-current={active ? 'page' : undefined}
              >
                {label}
              </Link>
            )
          })}
        </nav>
      </div>
    </header>
  )
}
