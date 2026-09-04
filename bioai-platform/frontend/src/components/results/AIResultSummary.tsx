'use client';

import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Brain, CircleNotch as Loader2, WarningCircle as AlertTriangle, CheckCircle, Info, ShieldCheck } from '@phosphor-icons/react';
import { fadeUp, fadeIn } from '@/lib/animations';
import { interpretToolResult, type AIInterpretation } from '@/lib/api';

interface AIResultSummaryProps {
  toolName: string;
  result: Record<string, unknown>;
  title?: string;
  compact?: boolean;
}

function numericTokens(value: string) {
  return value.match(/-?\d+(?:\.\d+)?(?:e[+-]?\d+)?%?/gi) ?? [];
}

function identifierTokens(value: string) {
  return value.match(/\b(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}|GO:\d{7}|IPR\d{6}|PF\d{5}|[0-9][A-Za-z0-9]{3})\b/gi) ?? [];
}

function normalizeNumber(token: string) {
  const raw = token.replace(/%$/, '');
  const value = Number(raw);
  return Number.isFinite(value) ? String(value) : raw.toLowerCase();
}

function isStructurallyGrounded(interpretation: AIInterpretation, result: Record<string, unknown>) {
  const source = JSON.stringify(result);
  const sourceNumbers = new Set(numericTokens(source).map(normalizeNumber));
  const sourceIds = new Set(identifierTokens(source).map((token) => token.toUpperCase()));
  const generated = [interpretation.headline, interpretation.summary, ...interpretation.findings, ...interpretation.caveats].join(' ');
  const generatedNumbers = numericTokens(generated).map(normalizeNumber);
  const generatedIds = identifierTokens(generated).map((token) => token.toUpperCase());
  return generatedNumbers.every((token) => sourceNumbers.has(token)) && generatedIds.every((token) => sourceIds.has(token));
}

export function AIResultSummary({
  toolName,
  result,
  title = 'AI Explanation',
  compact = false,
}: AIResultSummaryProps) {
  const [interpretation, setInterpretation] = useState<AIInterpretation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleInterpret = useCallback(async () => {
    if (loading) return;
    setLoading(true);
    setError(null);
    setInterpretation(null);
    try {
      const data = await interpretToolResult(toolName, result);
      if (!data?.summary?.trim()) throw new Error('AI explanation was empty and has been withheld.');
      if (!isStructurallyGrounded(data, result)) {
        throw new Error('AI explanation was withheld because it introduced a numeric value or structured identifier that is not present in the deterministic analysis result. Review the deterministic result instead.');
      }
      setInterpretation(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'AI explanation is unavailable. Use the deterministic result and provenance shown above.');
    } finally {
      setLoading(false);
    }
  }, [toolName, result, loading]);

  return (
    <motion.div variants={fadeUp} className="rounded-2xl border border-glass-border bg-surface-0 p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-accent-cyan" />
          <div><h3 className="font-semibold text-text-primary">{title}</h3><p className="mt-0.5 flex items-center gap-1 text-[10px] text-text-muted"><ShieldCheck className="h-3 w-3"/>Numeric values and structured biological identifiers are checked against the emitted result before display.</p></div>
        </div>
        {!interpretation && !loading && (
          <motion.button variants={fadeIn} onClick={handleInterpret} className="rounded-lg border border-accent-cyan/25 bg-accent-cyan/8 px-4 py-2 text-sm font-medium text-accent-cyan transition hover:bg-accent-cyan/12" disabled={loading}>
            Explain result
          </motion.button>
        )}
      </div>

      {error && !loading && <div className="mb-2 rounded-xl border border-warn/25 bg-warn/7 p-4"><p className="flex items-start gap-2 text-sm text-text-secondary"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" />{error}</p></div>}
      {loading && <div className="flex items-center gap-2 py-2 text-sm text-text-muted"><Loader2 className="h-4 w-4 animate-spin" />Generating an evidence-constrained explanation...</div>}

      {interpretation && !loading && <motion.div variants={fadeIn} className="space-y-4">
        <p className={`${compact ? 'text-base' : 'text-lg'} font-semibold text-text-primary`}>{interpretation.headline}</p>
        <p className={`${compact ? 'text-sm' : 'text-base'} leading-relaxed text-text-secondary`}>{interpretation.summary}</p>
        {interpretation.findings.length > 0 && <div><p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">Evidence-backed observations</p><ul className="space-y-1.5">{interpretation.findings.map((f, i) => <li key={`${f}-${i}`} className="flex items-start gap-2 text-sm text-text-secondary"><CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-good" />{f}</li>)}</ul></div>}
        {interpretation.caveats.length > 0 && <div><p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">Limitations</p><ul className="space-y-1.5">{interpretation.caveats.map((c, i) => <li key={`${c}-${i}`} className="flex items-start gap-2 text-sm text-text-secondary"><Info className="mt-0.5 h-4 w-4 shrink-0 text-warn" />{c}</li>)}</ul></div>}
        <div className="border-t border-glass-border pt-2"><button onClick={() => { setInterpretation(null); setError(null); }} className="text-xs text-text-muted transition hover:text-text-primary">Clear explanation</button></div>
      </motion.div>}
    </motion.div>
  );
}
