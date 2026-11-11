const configuredApiBaseUrl = (process.env.NEXT_PUBLIC_API_URL || '').trim().replace(/\/$/, '')
const developmentDefaultApiBaseUrl = 'http://127.0.0.1:8000'

export const API_BASE_URL =
  configuredApiBaseUrl || (process.env.NODE_ENV === 'development' ? developmentDefaultApiBaseUrl : '')

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return API_BASE_URL ? `${API_BASE_URL}${normalizedPath}` : normalizedPath
}

/** An API failure with a message that is safe to show. Raw server text is never used for server errors. */
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function friendly(status: number, detail: unknown): string {
  // Our API returns fixed, safe messages for these client errors.
  if ([409, 413, 415, 422].includes(status) && typeof detail === 'string' && detail.length <= 200) return detail
  if (status === 401 || status === 403) return 'Access denied. A valid API key is required.'
  if (status === 404) return 'Not found.'
  if (status === 429) return 'Too many requests. Wait a minute and try again.'
  if (status >= 500) return 'The service had a problem. Try again in a moment.'
  return `The request failed (${status}).`
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(apiUrl(path), init)
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check your connection and try again.')
  }
  if (!response.ok) {
    let detail: unknown
    try {
      detail = (await response.json())?.detail
    } catch {
      detail = undefined
    }
    throw new ApiError(response.status, friendly(response.status, detail))
  }
  return (await response.json()) as T
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : 'Something went wrong. Try again.'
}
