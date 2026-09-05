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

type NumericToken = { text: string; value: number };

const SUPERS: Record<string, string> = {
  '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁻': '-', '⁺': '+',
};

function normalizeText(value: string) {
  return value
    .replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]/g, (ch) => SUPERS[ch])
    .replace(/(\d)\s*,\s*(\d)/g, '$1$2')
    .replace(/(\d+(?:\.\d+)?)\s*[×✕*]\s*10\s*\^?\s*(-?\d+)/g, '$1e$2');
}

function numericTokens(value: string): NumericToken[] {
  return (normalizeText(value).match(/-?\d+(?:\.\d+)?(?:e[+-]?\d+)?%?/gi) ?? []).map((text) => ({
    text,
    value: Math.abs(parseFloat(text.replace(/%$/, ''))),
  }));
}

function nearlyEqual(a: number, b: number) {
  return Math.abs(a - b) <= 0.001 * Math.max(Math.abs(a), Math.abs(b), 1);
}

function isGrounded(value: number, sourceValues: NumericToken[]) {
  if (Number.isInteger(value) && value >= 0 && value <= 5) return true;
  return sourceValues.some(
    (s) => nearlyEqual(s.value, value) || nearlyEqual(s.value, value / 100) || nearlyEqual(s.value, value * 100),
  );
}

function checkNumericGrounding(
  interpretation: AIInterpretation,
  result: Record<string, unknown>,
): { grounded: boolean; ungrounded: string[] } {
  const sourceTokens = numericTokens(JSON.stringify(result));
  const generated = [interpretation.headline, interpretation.summary, ...interpretation.findings, ...interpretation.caveats].join(' ');
  const ungrounded = numericTokens(generated)
    .filter((token) => !isGrounded(token.value, sourceTokens))
    .map((token) => token.text);
  return { grounded: ungrounded.length === 0, ungrounded: [...new Set(ungrounded)].slice(0, 5) };
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
  const [warning, setWarning] = useState<string | null>(null);

  const handleInterpret = useCallback(async () => {
    if (loading) return;
    setLoading(true);
    setError(null);
    setWarning(null);
    setInterpretation(null);
    try {
      const data = await interpretToolResult(toolName, result);
      if (!data?.summary?.trim()) {
        setError('AI explanation was empty and has been withheld.');
        return;
      }
      const { grounded, ungrounded } = checkNumericGrounding(data, result);
      setInterpretation(data);
      if (!grounded) {
        setWarning(
          `Caution — value(s) ${ungrounded.join(', ')} in this explanation could not be traced to the raw result. Review the deterministic values above first.`,
        );
      }
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
          <div><h3 className="font-semibold text-text-primary">{title}</h3><p className="mt-0.5 flex items-center gap-1 text-[10px] text-text-muted"><ShieldCheck className="h-3 w-3"/>Numeric claims are checked against the emitted result before display.</p></div>
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
        {warning && <div className="rounded-xl border border-warn/25 bg-warn/7 p-4"><p className="flex items-start gap-2 text-sm text-text-secondary"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" />{warning}</p></div>}
        <p className={`${compact ? 'text-base' : 'text-lg'} font-semibold text-text-primary`}>{interpretation.headline}</p>
        <p className={`${compact ? 'text-sm' : 'text-base'} leading-relaxed text-text-secondary`}>{interpretation.summary}</p>
        {interpretation.findings.length > 0 && <div><p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">Evidence-backed observations</p><ul className="space-y-1.5">{interpretation.findings.map((f, i) => <li key={`${f}-${i}`} className="flex items-start gap-2 text-sm text-text-secondary"><CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-good" />{f}</li>)}</ul></div>}
        {interpretation.caveats.length > 0 && <div><p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">Limitations</p><ul className="space-y-1.5">{interpretation.caveats.map((c, i) => <li key={`${c}-${i}`} className="flex items-start gap-2 text-sm text-text-secondary"><Info className="mt-0.5 h-4 w-4 shrink-0 text-warn" />{c}</li>)}</ul></div>}
        <div className="border-t border-glass-border pt-2"><button onClick={() => { setInterpretation(null); setError(null); setWarning(null); }} className="text-xs text-text-muted transition hover:text-text-primary">Clear explanation</button></div>
      </motion.div>}
    </motion.div>
  );
}