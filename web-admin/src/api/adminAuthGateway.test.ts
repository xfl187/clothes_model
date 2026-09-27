import { afterEach, describe, expect, it, vi } from 'vitest';
import { AdminAuthGateway } from './adminAuthGateway';

const sessionBody = JSON.stringify({ authenticated: true, csrf_token: 'csrf-value-0000000000000000000000000000', created_at: '2026-09-27T00:00:00Z', expires_at: '2026-09-27T01:00:00Z' });

describe('AdminAuthGateway', () => {
  afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

  it('keeps credentials and csrf in memory while restoring and logging out', async () => {
    const requests: RequestInit[] = [];
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init: RequestInit) => {
      requests.push(init);
      return new Response(init.method === 'DELETE' ? null : sessionBody, { status: init.method === 'DELETE' ? 204 : init.method === 'POST' ? 201 : 200, headers: { 'Content-Type': 'application/json' } });
    }));
    const gateway = new AdminAuthGateway();
    await gateway.login('admin-secret-value-that-is-never-persisted');
    await gateway.restore();
    await gateway.logout();
    expect(requests.every(request => request.credentials === 'include')).toBe(true);
    expect(new Headers(requests[2]?.headers).get('X-CSRF-Token')).toContain('csrf-value');
    expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0);
  });
});
