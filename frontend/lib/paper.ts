import type { components } from '@/types/openapi';
export type PaperSession = components['schemas']['SessionResponse'];
export function modeLabel(mode: string): string {
  return mode === 'forward_paper'
    ? 'Forward paper · actual processing times'
    : mode === 'synthetic_demo'
      ? 'Synthetic demonstration · virtual clock'
      : 'Historical research replay';
}
export function paperActions(status: string, mode: string): string[] {
  if (mode === 'historical_replay') return status === 'STOPPED' ? [] : ['stop'];
  return (
    {
      CREATED: ['ready', 'stop'],
      READY: ['start', 'stop'],
      RUNNING: ['pause', 'stop', 'advance'],
      PAUSED: ['resume', 'stop'],
      FAILED: ['stop'],
      STOPPED: [],
    }[status] ?? []
  );
}
