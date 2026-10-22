import { it, expect, vi, afterEach } from 'vitest';
import {
  api,
  pageSchema,
  catalogSchema,
  ApiError,
  objectSchema,
  queryString,
} from '@/lib/api/client';
afterEach(() => vi.unstubAllGlobals());
it('validates real page structure without inventing missing items', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [{ metric: null }] }))),
  );
  expect((await api('/api/risk', pageSchema)).items[0].metric).toBeNull();
});
it.each([{}, { items: null }, { items: [1] }, '<html>bad</html>'])(
  'rejects malformed response %s',
  async (value) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(value))));
    await expect(api('/api/risk', pageSchema)).rejects.toThrow('unexpected data contract');
  },
);
it('surfaces API errors without exposing raw error payloads', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: { message: 'No snapshot at requested cutoff', secret: 'DO_NOT_ECHO' },
        }),
        { status: 404 },
      ),
    ),
  );
  await expect(api('/api/risk/x', objectSchema)).rejects.toEqual(
    new ApiError(404, 'No snapshot at requested cutoff'),
  );
});
it('passes cancellation through to fetch', async () => {
  const controller = new AbortController();
  const fetcher = vi.fn().mockImplementation((_url, { signal }) => {
    expect(signal).toBe(controller.signal);
    return Promise.reject(new DOMException('Aborted', 'AbortError'));
  });
  vi.stubGlobal('fetch', fetcher);
  controller.abort();
  await expect(api('/x', objectSchema, { signal: controller.signal })).rejects.toHaveProperty(
    'name',
    'AbortError',
  );
});
it('preserves pagination and safely encodes timestamps', () => {
  expect(pageSchema.parse({ items: [], next_offset: 20 }).next_offset).toBe(20);
  expect(queryString({ as_of: '2026-10-20T12:00:00+00:00' })).toContain('%2B00%3A00');
});
it('rejects malformed catalog links and unsupported kinds', () => {
  expect(
    catalogSchema.safeParse({ items: [{ id: 'x', kind: 'broker' }], next_offset: null }).success,
  ).toBe(false);
});
it('uses the same-origin proxy and JSON submission without credentials', async () => {
  const f = vi.fn().mockResolvedValue(new Response('{}'));
  vi.stubGlobal('fetch', f);
  await api('/api/risk/stress-test', objectSchema, { body: { scenario: 'hypothetical' } });
  expect(f.mock.calls[0][0]).toBe('/api/backend/api/risk/stress-test');
  expect(f.mock.calls[0][1].method).toBe('POST');
});
