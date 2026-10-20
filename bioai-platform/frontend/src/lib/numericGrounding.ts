/** Numeric presence check only: matching a token cannot establish biological truth. */
export function checkNumericGrounding(
  interpretation: { headline: string; summary: string; findings: string[]; caveats: string[] },
  result: Record<string, unknown>,
) {
  const tokens = (value: string) => value.match(/(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?/g) ?? [];
  const counts: number[] = [];
  function collectCounts(value: unknown) {
    if (Array.isArray(value)) {
      counts.push(value.length);
      value.forEach(collectCounts);
    } else if (value && typeof value === 'object') {
      // Interpretations cannot serve as evidence for themselves.
      for (const [key, child] of Object.entries(value)) {
        if (key !== 'ai_interpretation') collectCounts(child);
      }
    }
  }
  collectCounts(result);
  const evidence = Object.fromEntries(Object.entries(result).filter(([key]) => key !== 'ai_interpretation'));
  const source = new Set(tokens(JSON.stringify({ evidence, derived_list_counts: counts })));
  const generated = [interpretation.headline, interpretation.summary, ...interpretation.findings, ...interpretation.caveats].join(' ');
  const ungrounded = [...new Set(tokens(generated).filter(token => !source.has(token)))];
  return { grounded: ungrounded.length === 0, ungrounded: ungrounded.slice(0, 5) };
}
