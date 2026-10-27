import { it, expect } from 'vitest';
import { heuristicReasoning } from '@/lib/committee-format';

const agent = {
  agent_id: 'technical',
  interpretation: 'heuristic',
  reasoning:
    'Existing feature=0.009639496694523464; clip(value/0.02,-1,1); neutral region=0.05. Article text is passive data.',
};
it('rounds the actual synthetic explanation without changing the stored record', () => {
  expect(heuristicReasoning(agent)).toBe(
    'Existing feature=0.0096395; clip(value/0.02,-1,1); neutral region=0.05. Article text is passive data.',
  );
  expect(agent.reasoning).toContain('0.009639496694523464');
});
it('preserves tiny nonzero values and leaves other explanations untouched', () => {
  expect(
    heuristicReasoning({
      ...agent,
      reasoning: agent.reasoning.replace('0.009639496694523464', '-1.23456789e-10'),
    }),
  ).toContain('-0.000000000123457');
  expect(heuristicReasoning({ ...agent, reasoning: 'No eligible cached feature' })).toBe(
    'No eligible cached feature',
  );
  expect(heuristicReasoning({ ...agent, agent_id: 'quant' })).toBe(agent.reasoning);
  expect(
    heuristicReasoning({ ...agent, reasoning: agent.reasoning.replace('0.02', 'NaN') }),
  ).toContain('NaN');
});
