'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, Info, AlertCircle, X, ChevronUp } from 'lucide-react';
import type { AuditInsight } from '@/types/audit';

const SEVERITY_CONFIG = {
  info:     { border: 'border-accent-cyan/40',  bg: 'bg-accent-cyan/5',  icon: Info,          glow: '0 0 20px rgba(0,245,212,0.08)' },
  warning:  { border: 'border-yellow-500/40',   bg: 'bg-yellow-500/5',  icon: AlertTriangle,  glow: '0 0 20px rgba(234,179,8,0.08)' },
  critical: { border: 'border-red-500/40',      bg: 'bg-red-500/5',     icon: AlertCircle,    glow: '0 0 20px rgba(239,68,68,0.08)' },
} as const;

export function AuditInsightPanel({ sessionId }: { sessionId: string }) {
  const [insight, setInsight] = useState<AuditInsight | null>(null);
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    const poll = async () => {
      try {
        const r = await fetch(`/api/backend/audit/insights?session=${sessionId}`);
        if (!r.ok) return;
        const data = await r.json();
        if (data.latest) {
          const newInsight = data.latest as AuditInsight;
          setInsight((prev) => {
            if (prev?.id !== newInsight.id) {
              if (!open) setOpen(true);
              return newInsight;
            }
            return prev;
          });
        }
      } catch {}
    };
    poll();
    const interval = setInterval(poll, 10_000);
    return () => clearInterval(interval);
  }, [sessionId, open]);

  const handleClose = useCallback(() => {
    setOpen(false);
    setDismissed(true);
  }, []);

  if (dismissed && !open) return null;
  if (!insight) return null;

  const cfg = SEVERITY_CONFIG[insight.severity] ?? SEVERITY_CONFIG.info;
  const Icon = cfg.icon;

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          key="panel"
          initial={{ y: 80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 80, opacity: 0 }}
          transition={{ type: 'spring', damping: 28, stiffness: 260 }}
          className={`fixed bottom-6 right-6 z-50 w-80 p-4 rounded-xl border-l-4 ${cfg.border} ${cfg.bg}`}
          style={{
            background: 'rgba(10,10,22,0.92)',
            backdropFilter: 'blur(20px)',
            boxShadow: `0 8px 32px rgba(0,0,0,0.5), ${cfg.glow}`,
            border: '1px solid rgba(100,110,180,0.12)',
          }}
        >
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex items-center gap-2">
              <Icon size={14} className={cfg.border.replace('border-', 'text-').replace('/40', '')} />
              <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">AI Audit</span>
            </div>
            <button onClick={handleClose} className="text-text-muted hover:text-text-primary transition-colors">
              <X size={14} />
            </button>
          </div>
          <p className="text-xs text-text-primary leading-relaxed">{insight.insight}</p>
          {insight.suggestion && (
            <p className="text-xs mt-2 text-text-muted leading-relaxed">
              <span className="text-accent-cyan mr-1">&rarr;</span>
              {insight.suggestion}
            </p>
          )}
          {insight.affected_steps.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {insight.affected_steps.map((s) => (
                <span key={s} className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-text-muted font-mono">
                  {s}
                </span>
              ))}
            </div>
          )}
        </motion.div>
      ) : (
        <motion.button
          key="badge"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          exit={{ scale: 0 }}
          whileHover={{ scale: 1.05 }}
          onClick={() => { setOpen(true); setDismissed(false); }}
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-3 py-2 rounded-full"
          style={{
            background: 'rgba(10,10,22,0.9)',
            border: `1px solid ${cfg.border.replace('border-', '').replace('/40', '/40')}`,
            backdropFilter: 'blur(12px)',
            boxShadow: cfg.glow,
          }}
        >
          <Icon size={13} className={cfg.border.replace('border-', 'text-').replace('/40', '')} />
          <span className="text-xs font-medium text-text-primary">Audit</span>
          <ChevronUp size={11} className="text-text-muted" />
        </motion.button>
      )}
    </AnimatePresence>
  );
}
