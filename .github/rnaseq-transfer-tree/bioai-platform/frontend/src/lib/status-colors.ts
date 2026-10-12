/**
 * Single source of truth for job-status colours across the dashboard,
 * jobs, and history views.
 */

/** Icon colour per pipeline status. */
export const STATUS_TEXT: Record<string, string> = {
  queued: 'text-text-muted',
  submitted_to_ncbi: 'text-accent-cyan',
  polling_ncbi: 'text-accent-cyan',
  parsing: 'text-accent-cyan',
  interpreting: 'text-accent-cyan',
  running: 'text-accent-purple',
  complete: 'text-good',
  completed: 'text-good',
  failed: 'text-error',
};

/** Full badge styling (history list, chips). */
export const STATUS_BADGE: Record<string, string> = {
  complete: 'badge bg-good/10 text-good',
  completed: 'badge bg-good/10 text-good',
  running: 'badge bg-accent-purple/10 text-accent-purple',
  queued: 'badge bg-warn/10 text-warn',
  failed: 'badge bg-error/10 text-error',
};

export const ACTIVE_STATUSES = [
  'queued',
  'submitted_to_ncbi',
  'polling_ncbi',
  'parsing',
  'interpreting',
];
