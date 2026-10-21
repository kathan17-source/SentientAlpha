import { NextRequest } from 'next/server';

// Fixed server-only destination. Browser input can never select an upstream host.
async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (
    path.some((part) => part === '.' || part === '..' || !/^[a-zA-Z0-9_.-]+$/.test(part)) ||
    path.length > 8
  ) {
    return Response.json({ detail: 'Invalid API path' }, { status: 400 });
  }
  const route = '/' + path.join('/');
  const allowedPost =
    /^\/api\/paper\/sessions(?:\/[a-zA-Z0-9-]+\/(?:ready|start|pause|resume|stop|advance|update|reconcile|orders\/[a-zA-Z0-9-]+\/cancel))?$/.test(
      route,
    ) ||
    /^\/api\/(backtest|portfolio\/(optimize|efficient-frontier)|strategies\/discover|investment-committee\/analyze|risk\/stress-test)$/.test(
      route,
    ) ||
    /^\/api\/(backtest|investment-committee|portfolio\/optimization|risk\/decisions|strategies\/discovery|ml\/experiments)\/[a-zA-Z0-9-]+\/replay$/.test(
      route,
    );
  if (request.method === 'POST') {
    const origin = request.headers.get('origin');
    const trustedOrigins = (
      process.env.DASHBOARD_ORIGINS || 'http://127.0.0.1:3000,http://localhost:3000'
    ).split(',');
    if (!origin || !trustedOrigins.includes(origin) || !allowedPost) {
      return Response.json(
        { detail: 'This local research operation is not permitted' },
        { status: 403 },
      );
    }
    if (Number(request.headers.get('content-length') || 0) > 2 * 1024 * 1024) {
      return Response.json({ detail: 'Research request exceeds 2 MiB' }, { status: 413 });
    }
  }
  const base = process.env.API_BASE_URL || 'http://127.0.0.1:8000';
  try {
    let body: string | undefined;
    if (request.method === 'POST' && request.body) {
      const reader = request.body.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > 2 * 1024 * 1024) {
          await reader.cancel();
          return Response.json({ detail: 'Research request exceeds 2 MiB' }, { status: 413 });
        }
        chunks.push(value);
      }
      const bytes = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) {
        bytes.set(chunk, offset);
        offset += chunk.byteLength;
      }
      body = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
    }
    const response = await fetch(base + route + request.nextUrl.search, {
      method: request.method,
      headers: {
        Accept: 'application/json',
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body,
      cache: 'no-store',
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(120000)]),
    });
    const content = await response.text();
    return new Response(content, {
      status: response.status,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
    });
  } catch {
    return Response.json(
      {
        detail: {
          code: 'backend_unavailable',
          message: 'The local research backend is unavailable. Start FastAPI and retry.',
        },
      },
      { status: 503 },
    );
  }
}
export const GET = proxy;
export const POST = proxy;
