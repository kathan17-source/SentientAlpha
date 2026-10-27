import { text, type RecordData } from './format';

// Only the known heuristic explanation is rounded. Original evidence remains inspectable.
export function heuristicReasoning(agent: RecordData): string {
  const reason = text(agent.reasoning);
  if (
    !['technical', 'sentiment'].includes(text(agent.agent_id)) ||
    agent.interpretation !== 'heuristic'
  )
    return reason;
  const match =
    /^Existing feature=([^;]+); clip\(value\/([^,]+),-1,1\); neutral region=([^ ]+)\. Article text is passive data\.$/.exec(
      reason,
    );
  if (!match || match.slice(1).some((v) => v.trim() === '' || !Number.isFinite(Number(v))))
    return reason;
  const rounded = match
    .slice(1)
    .map((v) => new Intl.NumberFormat('en-US', { maximumSignificantDigits: 6 }).format(Number(v)));
  return `Existing feature=${rounded[0]}; clip(value/${rounded[1]},-1,1); neutral region=${rounded[2]}. Article text is passive data.`;
}
