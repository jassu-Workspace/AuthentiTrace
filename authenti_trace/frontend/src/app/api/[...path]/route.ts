// Server-side proxy to the backend, used in production when NEXT_PUBLIC_API_URL is not set.
// It adds the backend API key on the server, so the key never reaches the browser.
//
//   BACKEND_URL       where the API lives (default http://127.0.0.1:8000)
//   BACKEND_API_KEY   one of the backend's API_KEYS (optional when the backend runs without keys)
//
// Platform limits apply to the request body size (for example Vercel functions accept about 4.5 MB).
// For 50 MB uploads run the frontend on a host without that limit, or call the backend directly.
import type { NextRequest } from 'next/server'

export const dynamic = 'force-dynamic'

const BACKEND_URL = (process.env.BACKEND_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const API_KEY = process.env.BACKEND_API_KEY || ''

const FORWARD_REQUEST_HEADERS = ['content-type', 'content-length', 'accept', 'x-forwarded-for']
const FORWARD_RESPONSE_HEADERS = ['content-type', 'retry-after']

async function proxy(req: NextRequest): Promise<Response> {
  // The path is forwarded exactly as received (the backend's routes care about a trailing slash).
  // Only the versioned API is reachable, and no segment may climb out of it.
  const { pathname, search } = req.nextUrl
  const segments = pathname.split('/')
  if (!pathname.startsWith('/api/v1/') || segments.some((s, i) => s === '.' || s === '..' || (s === '' && i > 0 && i < segments.length - 1))) {
    return new Response('Not found', { status: 404 })
  }

  const headers = new Headers()
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = req.headers.get(name)
    if (value) headers.set(name, value)
  }
  if (API_KEY) headers.set('x-api-key', API_KEY)

  const hasBody = req.method !== 'GET' && req.method !== 'HEAD'
  let upstream: Response
  try {
    upstream = await fetch(`${BACKEND_URL}${pathname}${search}`, {
      method: req.method,
      headers,
      body: hasBody ? req.body : undefined,
      cache: 'no-store',
      redirect: 'manual', // never follow: a streamed body cannot be replayed
      // Node needs this to stream a request body
      ...(hasBody ? { duplex: 'half' } : {}),
    } as RequestInit)
  } catch {
    return Response.json({ detail: 'Backend unavailable' }, { status: 502 })
  }

  const responseHeaders = new Headers()
  for (const name of FORWARD_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name)
    if (value) responseHeaders.set(name, value)
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders })
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE }
