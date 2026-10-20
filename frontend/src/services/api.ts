/**
 * API client. Attaches the short-lived access token, transparently refreshes
 * it (with rotation) on 401s, and normalises backend error envelopes:
 *   { "error": { code, message, details } }
 *
 * The API base is relative (same-origin / Vite proxy) so the app works behind
 * any preview host without hardcoded localhost URLs.
 */
import type { ApiError, TokenResponse } from '../types';

const API_BASE = '/api/v1';

const ACCESS_KEY = 'mpis_access';
const REFRESH_KEY = 'mpis_refresh';
const USER_KEY = 'mpis_user';

export class ApiRequestError extends Error {
  status: number;
  error: ApiError;
  constructor(status: number, error: ApiError) {
    super(error.message);
    this.status = status;
    this.error = error;
  }
}

export const tokenStore = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(tokens: { access_token: string; refresh_token: string }) {
    localStorage.setItem(ACCESS_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
  },
};

let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const refresh = tokenStore.refresh;
  if (!refresh) return false;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const data = (await res.json()) as TokenResponse;
    tokenStore.set({ access_token: data.access_token, refresh_token: data.refresh_token });
    return true;
  } catch {
    return false;
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(options.headers || {});
  const access = tokenStore.access;
  if (access) headers.set('Authorization', `Bearer ${access}`);
  if (!(options.body instanceof FormData) && !headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 && retry && tokenStore.refresh) {
    refreshPromise = refreshPromise ?? tryRefresh().finally(() => (refreshPromise = null));
    const ok = await refreshPromise;
    if (ok) return api<T>(path, options, false);
    tokenStore.clear();
  }

  if (res.status === 204) return undefined as T;

  const isJson = res.headers.get('content-type')?.includes('application/json');
  const body = isJson ? await res.json() : await res.blob();

  if (!res.ok) {
    const err = (body as { error?: ApiError })?.error ?? {
      code: 'http_error',
      message: `Request failed with status ${res.status}`,
      details: {},
    };
    throw new ApiRequestError(res.status, err);
  }
  return body as T;
}

export const apiGet = <T>(path: string) => api<T>(path);
export const apiPost = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'POST', body: body instanceof FormData ? body : JSON.stringify(body ?? {}) });
export const apiPatch = <T>(path: string, body: unknown) =>
  api<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
export const apiPut = <T>(path: string, body: unknown) =>
  api<T>(path, { method: 'PUT', body: JSON.stringify(body) });
export const apiDelete = <T>(path: string) => api<T>(path, { method: 'DELETE' });

/** Authenticated binary download (photos, PDF/CSV reports). */
export async function apiDownload(path: string, filename: string): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${tokenStore.access}` },
  });
  if (!res.ok) throw new ApiRequestError(res.status, { code: 'download_failed', message: 'Download failed', details: {} });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function photoUrl(caseId: string, photoId: string): string {
  // The <img> can't attach headers; the backend also accepts ?token= — we use
  // the authenticated fetch in <PhotoImg> instead.
  return `${API_BASE}/cases/${caseId}/photos/${photoId}/file`;
}

export async function fetchPhotoBlob(caseId: string, photoId: string): Promise<string> {
  const res = await fetch(photoUrl(caseId, photoId), {
    headers: { Authorization: `Bearer ${tokenStore.access}` },
  });
  if (!res.ok) return '';
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
