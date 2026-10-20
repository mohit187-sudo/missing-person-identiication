import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { api, ApiRequestError, tokenStore } from '../../frontend/src/services/api';

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => body,
  };
}

describe('api client', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it('attaches the bearer token to requests', async () => {
    tokenStore.set({ access_token: 'abc', refresh_token: 'def' });
    fetchMock.mockResolvedValueOnce(jsonResponse({ ok: true }));
    await api('/auth/me');
    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Headers).get('Authorization')).toBe('Bearer abc');
  });

  it('normalises backend error envelopes into ApiRequestError', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ error: { code: 'forbidden', message: 'Nope', details: { a: 1 } } }, 403),
    );
    await expect(api('/cases')).rejects.toMatchObject({
      status: 403,
      error: { code: 'forbidden', message: 'Nope' },
    });
  });

  it('throws ApiRequestError instances', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ error: { code: 'not_found', message: 'Missing', details: {} } }, 404),
    );
    try {
      await api('/cases/xyz');
      expect.fail('should throw');
    } catch (e) {
      expect(e).toBeInstanceOf(ApiRequestError);
    }
  });

  it('refreshes the token once on 401 and retries', async () => {
    tokenStore.set({ access_token: 'stale', refresh_token: 'refresh-1' });
    // First call: 401. Refresh call: new tokens. Retry: success.
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({ error: { code: 'unauthorized', message: 'expired', details: {} } }, 401),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: 'fresh',
          refresh_token: 'refresh-2',
          token_type: 'bearer',
          expires_in: 900,
          user: {},
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ hello: 'world' }));

    const result = await api<{ hello: string }>('/stats/overview');
    expect(result.hello).toBe('world');
    expect(tokenStore.access).toBe('fresh');
    expect(tokenStore.refresh).toBe('refresh-2');
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it('clears the session when refresh fails', async () => {
    tokenStore.set({ access_token: 'stale', refresh_token: 'bad' });
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({ error: { code: 'unauthorized', message: 'expired', details: {} } }, 401),
      )
      .mockResolvedValueOnce(
        jsonResponse({ error: { code: 'unauthorized', message: 'gone', details: {} } }, 401),
      );

    await expect(api('/auth/me')).rejects.toBeTruthy();
    expect(tokenStore.access).toBeNull();
    expect(tokenStore.refresh).toBeNull();
  });
});
