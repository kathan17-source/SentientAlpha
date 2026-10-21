import { afterEach, it, expect, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { GET, POST } from '@/app/api/backend/[...path]/route';
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
const context = (path: string[]) => ({ params: Promise.resolve({ path }) });
it('allows explicit local origin despite Next canonical-host differences', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(Response.json({ id: 'actual-backend-response' }, { status: 201 })),
  );
  const r = await POST(
    new NextRequest('http://localhost:3000/api/backend/api/risk/stress-test', {
      method: 'POST',
      headers: { origin: 'http://127.0.0.1:3000', 'content-type': 'application/json' },
      body: '{}',
    }),
    context(['api', 'risk', 'stress-test']),
  );
  expect(r.status).toBe(201);
});
it.each(['https://evil.invalid', 'null', ''])(
  'rejects untrusted mutation origin %s',
  async (origin) => {
    const fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    const r = await POST(
      new NextRequest('http://localhost:3000/api/backend/api/risk/stress-test', {
        method: 'POST',
        headers: { origin },
        body: '{}',
      }),
      context(['api', 'risk', 'stress-test']),
    );
    expect(r.status).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
  },
);
it('does not expose live execution or arbitrary mutation routes', async () => {
  const r = await POST(
    new NextRequest('http://localhost:3000/api/backend/api/orders/execute', {
      method: 'POST',
      headers: { origin: 'http://127.0.0.1:3000' },
      body: '{}',
    }),
    context(['api', 'orders', 'execute']),
  );
  expect(r.status).toBe(403);
});
it('rejects traversal before an upstream request', async () => {
  const fetcher = vi.fn();
  vi.stubGlobal('fetch', fetcher);
  const r = await GET(
    new NextRequest('http://localhost:3000/api/backend/x'),
    context(['..', 'secret']),
  );
  expect(r.status).toBe(400);
  expect(fetcher).not.toHaveBeenCalled();
});
it('fixes the server destination and never forwards cookies or browser credentials', async () => {
  vi.stubEnv('API_BASE_URL', 'http://127.0.0.1:8100');
  const f = vi.fn().mockResolvedValue(Response.json({ items: [] }));
  vi.stubGlobal('fetch', f);
  await GET(
    new NextRequest('http://localhost:3000/api/backend/api/assets', {
      headers: { cookie: 'private-local-cookie' },
    }),
    context(['api', 'assets']),
  );
  expect(f.mock.calls[0][0]).toBe('http://127.0.0.1:8100/api/assets');
  expect(f.mock.calls[0][1].headers.cookie).toBeUndefined();
});
it('returns a sanitized actionable error for an unavailable backend', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private connection details')));
  const r = await GET(
    new NextRequest('http://localhost:3000/api/backend/ready'),
    context(['ready']),
  );
  expect(r.status).toBe(503);
  expect(JSON.stringify(await r.json())).not.toContain('private connection details');
});
it('rejects oversized mutation before forwarding', async () => {
  const f = vi.fn();
  vi.stubGlobal('fetch', f);
  const r = await POST(
    new NextRequest('http://localhost:3000/api/backend/api/risk/stress-test', {
      method: 'POST',
      headers: { origin: 'http://127.0.0.1:3000', 'content-length': '3000000' },
      body: '{}',
    }),
    context(['api', 'risk', 'stress-test']),
  );
  expect(r.status).toBe(413);
  expect(f).not.toHaveBeenCalled();
});
