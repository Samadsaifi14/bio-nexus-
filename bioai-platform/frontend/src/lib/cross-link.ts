import type { AppRouterInstance } from 'next/dist/shared/lib/app-router-context.shared-runtime';

const ANALYSIS_CONTEXT_KEY = 'bionexus_analysis_context_v1';
const ANALYSIS_CONTEXT_MAX_AGE_MS = 12 * 60 * 60 * 1000;

export type AnalysisHandoff = {
  version: 1;
  sourceTool?: string;
  sourceJobId?: string;
  updatedAt: number;
  querySequence?: string;
  sequenceType?: 'protein' | 'dna' | 'rna' | 'unknown';
  queryAccession?: string;
  resolvedAccession?: string;
  resolvedSequence?: string;
  topHitAccession?: string;
  topHitSequence?: string;
  geneName?: string;
  organism?: string;
  pdbId?: string;
  pdbUrl?: string;
  structureSource?: string;
  structureType?: string;
  msaFasta?: string;
  phyloNewick?: string;
  pathwayIdentifiers?: string[];
  blastProgram?: string;
  blastDatabase?: string;
};

function storageAvailable(): boolean {
  return typeof window !== 'undefined' && typeof sessionStorage !== 'undefined';
}

function sanitizeHandoff(raw: unknown): AnalysisHandoff | null {
  if (!raw || typeof raw !== 'object') return null;
  const value = raw as Partial<AnalysisHandoff>;
  if (value.version !== 1 || typeof value.updatedAt !== 'number') return null;
  if (Date.now() - value.updatedAt > ANALYSIS_CONTEXT_MAX_AGE_MS) return null;
  return value as AnalysisHandoff;
}

/**
 * Read the current analysis handoff without consuming it.
 *
 * This is intentionally persistent for the current browser tab so users can
 * chain several scientific tools without repeatedly copying identifiers,
 * sequences, or structures. The payload expires after 12 hours and is replaced
 * when a new analysis handoff is started.
 */
export function getAnalysisHandoff(): AnalysisHandoff | null {
  if (!storageAvailable()) return null;
  const raw = sessionStorage.getItem(ANALYSIS_CONTEXT_KEY);
  if (!raw) return null;
  try {
    const parsed = sanitizeHandoff(JSON.parse(raw));
    if (!parsed) sessionStorage.removeItem(ANALYSIS_CONTEXT_KEY);
    return parsed;
  } catch {
    sessionStorage.removeItem(ANALYSIS_CONTEXT_KEY);
    return null;
  }
}

export function setAnalysisHandoff(
  patch: Partial<Omit<AnalysisHandoff, 'version' | 'updatedAt'>>,
  options: { replace?: boolean } = {},
): AnalysisHandoff | null {
  if (!storageAvailable()) return null;
  const base = options.replace ? null : getAnalysisHandoff();
  const next: AnalysisHandoff = {
    version: 1,
    ...(base ?? {}),
    ...patch,
    updatedAt: Date.now(),
  };
  sessionStorage.setItem(ANALYSIS_CONTEXT_KEY, JSON.stringify(next));
  return next;
}

export function clearAnalysisHandoff() {
  if (!storageAvailable()) return;
  sessionStorage.removeItem(ANALYSIS_CONTEXT_KEY);
}

/**
 * Consume a one-shot sessionStorage pre-fill param.
 * Reads the value and immediately removes it so it can't be re-used on refresh.
 */
export function consumeParam(key: string): string | null {
  if (!storageAvailable()) return null;
  const v = sessionStorage.getItem(key);
  if (v !== null) sessionStorage.removeItem(key);
  return v;
}

/**
 * Set a pre-fill param in sessionStorage and navigate to the target route.
 * The target page should call `consumeParam(key)` on mount.
 */
export function setPrefill(
  router: AppRouterInstance,
  key: string,
  value: string,
  target: string,
) {
  if (!storageAvailable()) return;
  sessionStorage.setItem(key, value);
  router.push(target);
}

/**
 * Persist a structured analysis context and optional legacy one-shot fields,
 * then navigate. This is the preferred cross-tool handoff for BioNexus.
 */
export function continueAnalysis(
  router: AppRouterInstance,
  context: Partial<Omit<AnalysisHandoff, 'version' | 'updatedAt'>>,
  target: string,
  legacyPrefills: Record<string, string | undefined | null> = {},
) {
  if (!storageAvailable()) return;
  setAnalysisHandoff(context);
  for (const [key, value] of Object.entries(legacyPrefills)) {
    if (value) sessionStorage.setItem(key, value);
  }
  router.push(target);
}
