import { z } from 'zod';
import type { components } from '@/types/openapi';

export type CatalogItem = components['schemas']['CatalogItem'];
export type CatalogKind = CatalogItem['kind'];
export type CommitteeRun = components['schemas']['sentientalpha__api__committee__RunResponse'];
export type RiskAssessment = components['schemas']['AssessmentResponse'];
export const objectSchema = z.record(z.string(), z.unknown());
export const pageSchema = z.object({
  items: z.array(objectSchema),
  next_offset: z.number().int().nonnegative().nullable().optional(),
});
export const catalogSchema = z.object({
  items: z.array(
    z.object({
      id: z.string().min(1),
      kind: z.enum([
        'backtest',
        'optimization',
        'ml',
        'strategy',
        'committee',
        'features',
        'sentiment',
      ]),
      status: z.string(),
      created_at: z.string(),
      label: z.string(),
      configuration: objectSchema,
      links: z.record(z.string(), z.string()),
    }),
  ),
  next_offset: z.number().nullable(),
});
export const riskSchema = z.object({
  id: z.string(),
  portfolio_id: z.string(),
  at: z.string(),
  status: z.string(),
  phase: z.string(),
  policy_key: z.string(),
  committee_id: z.string().nullable(),
  backtest_id: z.string().nullable(),
  payload: objectSchema,
});
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
export async function api<T>(
  path: string,
  schema: z.ZodType<T>,
  options: { signal?: AbortSignal; body?: unknown } = {},
): Promise<T> {
  const response = await fetch('/api/backend' + path, {
    signal: options.signal,
    method: options.body === undefined ? 'GET' : 'POST',
    headers: {
      Accept: 'application/json',
      ...(options.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
  });
  const raw: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = z.object({ detail: z.unknown() }).safeParse(raw);
    const detail = error.success ? error.data.detail : null;
    const message =
      typeof detail === 'string'
        ? detail
        : z.object({ message: z.string() }).safeParse(detail).data?.message;
    throw new ApiError(
      response.status,
      message || `Research service returned ${response.status}. Check the request and retry.`,
    );
  }
  const result = schema.safeParse(raw);
  if (!result.success)
    throw new ApiError(
      502,
      'The research service returned an unexpected data contract. No values were substituted.',
    );
  return result.data;
}
export const queryString = (params: Record<string, string | number | undefined>) =>
  new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)]),
  ).toString();
