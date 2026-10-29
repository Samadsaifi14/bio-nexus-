'use client';

import { useCallback, useMemo, useRef } from 'react';
import { useAuth } from '@/contexts/auth';
import type { AuditEvent } from '@/types/audit';

const SESSION_ID = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
const compact = (value: string) => value.replace(/\s+/g, ' ').replace(/\b[ACDEFGHIKLMNPQRSTVWYBXZJUO]{24,}\b/gi, '[sequence-redacted]').replace(/https?:\/\/\S+/gi, '[url-redacted]').trim().slice(0, 240);
const HISTORY_KEY = 'omvetra.analysis-history.v1';
const newAnalysisId = () => typeof crypto !== 'undefined' && crypto.randomUUID
  ? crypto.randomUUID()
  : `ana-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

function saveAnalysisEvent(event: AuditEvent, analysisId: string) {
  if (typeof window === 'undefined') return;
  try {
    const current = JSON.parse(window.localStorage.getItem(HISTORY_KEY) || '[]') as Array<Record<string, unknown>>;
    const existing = current.findIndex((item) => item.analysis_id === analysisId);
    const previous = existing >= 0 ? current[existing] : {};
    const next = {
      ...previous,
      analysis_id: analysisId,
      tool: event.tool,
      step: event.step,
      status: event.status,
      input_summary: event.input_summary,
      output_summary: event.output_summary,
      duration_ms: event.duration_ms,
      updated_at: event.timestamp,
      user_id: event.user_id,
      session_id: event.session_id,
    };
    const history = [next, ...current.filter((item) => item.analysis_id !== analysisId)].slice(0, 100);
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    window.dispatchEvent(new CustomEvent('omvetra:analysis-history-updated', { detail: next }));
  } catch {
    // Storage can be disabled or full; analysis must still run.
  }
}

export function useAuditTrail() {
  const { user } = useAuth();
  const t0Ref = useRef<Record<string, number>>({});
  const idRef = useRef<Record<string, string>>({});
  const emit = useCallback(async (event: Omit<AuditEvent, 'session_id' | 'timestamp'>) => {
    const body: AuditEvent = { ...event, input_summary: compact(event.input_summary || ''), output_summary: compact(event.output_summary || ''), session_id: SESSION_ID, user_id: user?.id ?? null, timestamp: new Date().toISOString() };
    const analysisId = event.metadata?.analysis_id;
    if (typeof analysisId === 'string') saveAnalysisEvent(body, analysisId);
    fetch('/api/backend/api/audit/event', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), keepalive: true }).catch(() => {});
  }, [user?.id]);
  const emitStarted = useCallback((step: string, tool: string, input_summary: string) => {
    const analysisId = newAnalysisId(); idRef.current[`${step}-${tool}`] = analysisId; t0Ref.current[`${step}-${tool}`] = Date.now();
    emit({ step, tool, status: 'started', input_summary, output_summary: '', duration_ms: 0, user_id: user?.id ?? null, metadata: { analysis_id: analysisId } });
  }, [emit, user?.id]);
  const emitSuccess = useCallback((step: string, tool: string, input_summary: string, output_summary: string) => {
    const key = `${step}-${tool}`; const t0 = t0Ref.current[key] ?? Date.now(); delete t0Ref.current[key];
    const analysisId = idRef.current[key] ?? newAnalysisId(); delete idRef.current[key];
    emit({ step, tool, status: 'success', input_summary, output_summary, duration_ms: Date.now() - t0, user_id: user?.id ?? null, metadata: { analysis_id: analysisId } });
  }, [emit, user?.id]);
  const emitFailed = useCallback((step: string, tool: string, input_summary: string, error: string) => {
    const key = `${step}-${tool}`; const t0 = t0Ref.current[key] ?? Date.now(); delete t0Ref.current[key];
    const analysisId = idRef.current[key] ?? newAnalysisId(); delete idRef.current[key];
    emit({ step, tool, status: 'failed', input_summary, output_summary: error, duration_ms: Date.now() - t0, user_id: user?.id ?? null, metadata: { analysis_id: analysisId } });
  }, [emit, user?.id]);
  return useMemo(() => ({ emit, emitStarted, emitSuccess, emitFailed, SESSION_ID }), [emit, emitStarted, emitSuccess, emitFailed]);
}
