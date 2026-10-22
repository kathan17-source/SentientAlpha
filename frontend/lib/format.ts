export type Numeric = number | string | null | undefined;
export function finite(value: unknown): number | null {
  if (typeof value !== 'number' && typeof value !== 'string') return null;
  if (typeof value === 'string' && value.trim() === '') return null;
  const result = Number(value);
  return Number.isFinite(result) ? result : null;
}
export function money(value: Numeric, digits = 2): string {
  const n = finite(value);
  return n === null
    ? 'Unavailable'
    : new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }).format(n);
}
export function percent(value: Numeric, digits = 2): string {
  const n = finite(value);
  return n === null
    ? 'Unavailable'
    : new Intl.NumberFormat('en-US', {
        style: 'percent',
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }).format(n);
}
export function decimal(value: Numeric, digits = 2): string {
  const n = finite(value);
  return n === null
    ? 'Unavailable'
    : new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(n);
}
export const bps = (value: Numeric) =>
  finite(value) === null ? 'Unavailable' : `${decimal(finite(value)! * 10000)} bps`;
export function timestamp(value: unknown): string {
  if (typeof value !== 'string' || !value || !/(Z|[+-]\d{2}:\d{2})$/.test(value))
    return 'Unavailable';
  const d = new Date(value);
  return Number.isFinite(d.getTime())
    ? d.toISOString().replace('T', ' ').replace('.000Z', ' UTC').replace('Z', ' UTC')
    : 'Unavailable';
}
export const shortId = (value: unknown) =>
  typeof value === 'string' ? value.slice(0, 8) : 'Unavailable';
export type RecordData = Record<string, unknown>;
export const record = (v: unknown): RecordData =>
  v !== null && typeof v === 'object' && !Array.isArray(v) ? (v as RecordData) : {};
export const records = (v: unknown): RecordData[] => (Array.isArray(v) ? v.map(record) : []);
export const text = (v: unknown, fallback = 'Unavailable'): string =>
  typeof v === 'string' ? v : fallback;
export const valueAt = (v: unknown, ...keys: string[]): unknown =>
  keys.reduce<unknown>((o, k) => record(o)[k], v);
export function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2) ?? 'Unavailable';
}
