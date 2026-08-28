'use client';

import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Brain, CircleNotch as Loader2, WarningCircle as AlertTriangle, CheckCircle, Info } from '@phosphor-icons/react';
import { fadeUp, fadeIn, cardHover } from '@/lib/animations';
import { interpretToolResult, type AIInterpretation } from '@/lib/api';

interface AIResultSummaryProps {
  toolName: string;
  result: Record<string, unknown>;
  title?: string;
  compact?: boolean;
}

export function AIResultSummary({
  toolName,
  result,
  title = 'AI Interpretation',
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
      setInterpretation(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'AI summary failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [toolName, result, loading]);

  return (
    <motion.div
      variants={fadeUp}
      whileHover={cardHover}
      className="bg-accent-cyan/[0.06] rounded-2xl border border-accent-cyan/20 p-5"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-accent-cyan" />
          <h3 className="font-semibold text-text-primary">{title}</h3>
        </div>
        {!interpretation && !loading && (
          <motion.button
            variants={fadeIn}
            onClick={handleInterpret}
            className="px-4 py-2 bg-accent-cyan text-void text-sm font-medium rounded-lg hover:bg-accent-hover transition disabled:opacity-50"
            disabled={loading}
          >
            Interpret with AI
          </motion.button>
        )}
      </div>

      {error && !loading && (
        <div className="bg-error/10 border border-error/30 rounded-xl p-4 mb-2">
          <p className="text-sm text-error flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            {error}
          </p>
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-sm text-text-muted py-2">
          <Loader2 className="w-4 h-4 animate-spin" />
          Summarizing your results in plain language...
        </div>
      )}

      {interpretation && !loading && (
        <motion.div variants={fadeIn} className="space-y-4">
          <p className={`${compact ? 'text-base' : 'text-lg'} font-semibold text-text-primary`}>
            {interpretation.headline}
          </p>
          <p className={`${compact ? 'text-sm' : 'text-base'} text-text-secondary leading-relaxed`}>
            {interpretation.summary}
          </p>

          {interpretation.findings.length > 0 && (
            <div>
              <p className="text-xs uppercase tracking-wide text-text-muted mb-2 font-medium">Key findings</p>
              <ul className="space-y-1.5">
                {interpretation.findings.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                    <CheckCircle className="w-4 h-4 text-good shrink-0 mt-0.5" />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {interpretation.caveats.length > 0 && (
            <div>
              <p className="text-xs uppercase tracking-wide text-text-muted mb-2 font-medium">
                Things to keep in mind
              </p>
              <ul className="space-y-1.5">
                {interpretation.caveats.map((c, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                    <Info className="w-4 h-4 text-accent-amber shrink-0 mt-0.5" />
                    {c}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex items-center justify-between pt-2 border-t border-accent-cyan/20">
            <button
              onClick={() => { setInterpretation(null); setError(null); }}
              className="text-xs text-text-muted hover:text-text-primary transition"
            >
              Regenerate
            </button>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
