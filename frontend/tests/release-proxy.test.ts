import { afterEach, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { POST } from '@/app/api/backend/[...path]/route';
afterEach(() => vi.unstubAllGlobals());
it('bounds bodies without Content-Length before contacting the backend', async () => {
  const upstream = vi.fn();
  vi.stubGlobal('fetch', upstream);
  const request = new NextRequest('http://localhost:3000/api/backend/api/risk/stress-test', {
    method: 'POST',
    headers: { origin: 'http://127.0.0.1:3000' },
    body: 'x'.repeat(2 * 1024 * 1024 + 1),
  });
  const response = await POST(request, {
    params: Promise.resolve({ path: ['api', 'risk', 'stress-test'] }),
  });
  expect(response.status).toBe(413);
  expect(upstream).not.toHaveBeenCalled();
});
