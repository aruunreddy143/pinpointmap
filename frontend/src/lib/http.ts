// Small fetch wrapper for the PINPOINT API.
// The access token lives in memory only (never localStorage). The refresh token is an httpOnly
// cookie set by the backend, so page scripts cannot read it.

export const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000'

let accessToken: string | null = null
export const setAccessToken = (t: string | null) => {
  accessToken = t
}
export const getAccessToken = () => accessToken

/** Called once when a signed-in request gets a 401; returns true if a fresh token is now held. */
let onUnauthorized: (() => Promise<boolean>) | null = null
export const setUnauthorizedHandler = (fn: (() => Promise<boolean>) | null) => {
  onUnauthorized = fn
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  /** Parsed JSON body of the error response, when there was one. */
  readonly body: unknown
  constructor(status: number, code: string, message: string, body?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.body = body
  }
}

interface Options {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH'
  body?: unknown
  /** Send the Authorization header when a token is held. */
  auth?: boolean
  /** Cookie-based endpoints (refresh, logout) require this header. */
  csrf?: boolean
}

export interface ApiResult<T> {
  status: number
  data: T
}

async function send(path: string, { method = 'GET', body, auth = false, csrf = false }: Options, retried: boolean): Promise<Response> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth && accessToken) headers.Authorization = `Bearer ${accessToken}`
  if (csrf) headers['X-Pinpoint-Csrf'] = '1'
  let res: Response
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      credentials: 'include',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'network', 'Could not reach the server. Check your connection and try again.')
  }
  if (res.status === 401 && auth && accessToken && !retried && onUnauthorized && (await onUnauthorized())) {
    return send(path, { method, body, auth, csrf }, true)
  }
  return res
}

async function toError(res: Response): Promise<ApiError> {
  const text = await res.text()
  let json: unknown = undefined
  try {
    json = text ? JSON.parse(text) : undefined
  } catch {
    /* non-JSON body */
  }
  const err = (json ?? {}) as { error?: string; message?: string; detail?: unknown }
  // AppError => {error, message}. FastAPI validation => {detail: [...]}.
  const invalid = Array.isArray(err.detail)
  const message = err.message ?? (invalid ? 'Please check the details you entered.' : 'Something went wrong. Please try again.')
  return new ApiError(res.status, err.error ?? (invalid ? 'invalid_input' : 'error'), message, json)
}

export async function apiRequest<T>(path: string, options: Options = {}): Promise<ApiResult<T>> {
  const res = await send(path, options, false)
  if (!res.ok) throw await toError(res)
  const text = res.status === 204 ? '' : await res.text()
  let json: unknown = undefined
  if (text) {
    try {
      json = JSON.parse(text)
    } catch {
      /* non-JSON body */
    }
  }
  return { status: res.status, data: json as T }
}

/** For endpoints that return a file (labels). */
export async function apiBlob(path: string): Promise<Blob> {
  const res = await send(path, { auth: true }, false)
  if (!res.ok) throw await toError(res)
  return res.blob()
}
