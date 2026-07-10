'use client';

import { useCallback, useMemo, useRef } from 'react';
import { useAuth } from '@/contexts/auth';
import type { AuditEvent } from '@/types/audit';

const SESSION_ID = typeof crypto !== 'undefined' && crypto.randomUUID
  ? crypto.randomUUID()
  : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

export function useAuditTrail() {
  const { user, isGuest } = useAuth();
  const t0Ref = useRef<Record<string, number>>({});

  const emit = useCallback(async (event: Omit<AuditEvent, 'session_id' | 'timestamp'>) => {
    const body: AuditEvent = {
      ...event,
      session_id: SESSION_ID,
      user_id: user?.id ?? null,
      timestamp: new Date().toISOString(),
    };
    fetch('/api/backend/audit/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).catch(() => {});
  }, [user?.id]);

  const emitStarted = useCallback((step: string, tool: string, input_summary: string) => {
    const key = `${step}-${tool}`;
    t0Ref.current[key] = Date.now();
    emit({ step, tool, status: 'started', input_summary, output_summary: '', duration_ms: 0, user_id: user?.id ?? null });
  }, [emit, user?.id]);

  const emitSuccess = useCallback((step: string, tool: string, input_summary: string, output_summary: string) => {
    const key = `${step}-${tool}`;
    const t0 = t0Ref.current[key] ?? Date.now();
    delete t0Ref.current[key];
    emit({ step, tool, status: 'success', input_summary, output_summary, duration_ms: Date.now() - t0, user_id: user?.id ?? null });
  }, [emit, user?.id]);

  const emitFailed = useCallback((step: string, tool: string, input_summary: string, error: string) => {
    const key = `${step}-${tool}`;
    const t0 = t0Ref.current[key] ?? Date.now();
    delete t0Ref.current[key];
    emit({ step, tool, status: 'failed', input_summary, output_summary: error, duration_ms: Date.now() - t0, user_id: user?.id ?? null });
  }, [emit, user?.id]);

  return useMemo(() => ({ emit, emitStarted, emitSuccess, emitFailed, SESSION_ID }), [emit, emitStarted, emitSuccess, emitFailed]);
}
