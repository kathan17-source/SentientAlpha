import { it, expect, vi, afterEach } from 'vitest';
import { NextRequest } from 'next/server';
import { POST } from '@/app/api/backend/[...path]/route';
afterEach(() => vi.unstubAllGlobals());
const context = (path: string[]) => ({ params: Promise.resolve({ path }) });
it('allows bounded paper controls while rejecting arbitrary order submissions', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ status: 'PAUSED' })));
  const allowed = await POST(
    new NextRequest('http://localhost:3000/api/backend/api/paper/sessions/session-id/pause', {
      method: 'POST',
      headers: { origin: 'http://127.0.0.1:3000' },
      body: '{"key":"command-key"}',
    }),
    context(['api', 'paper', 'sessions', 'session-id', 'pause']),
  );
  expect(allowed.status).toBe(200);
  const denied = await POST(
    new NextRequest('http://localhost:3000/api/backend/api/paper/sessions/session-id/orders', {
      method: 'POST',
      headers: { origin: 'http://127.0.0.1:3000' },
      body: '{}',
    }),
    context(['api', 'paper', 'sessions', 'session-id', 'orders']),
  );
  expect(denied.status).toBe(403);
});
