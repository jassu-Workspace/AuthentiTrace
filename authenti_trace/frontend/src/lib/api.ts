const configuredApiBaseUrl = (process.env.NEXT_PUBLIC_API_URL || '').trim().replace(/\/$/, '')
const developmentDefaultApiBaseUrl = 'http://localhost:8000'

export const API_BASE_URL =
  configuredApiBaseUrl || (process.env.NODE_ENV === 'development' ? developmentDefaultApiBaseUrl : '')

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return API_BASE_URL ? `${API_BASE_URL}${normalizedPath}` : normalizedPath
}
