import type { StreamEvent } from '@/types/results';

export function safeInterpretationHref(value: string): string | null {
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function parseEvent(data: string[]): StreamEvent | null {
  if (!data.length) return null;
  const value: unknown = JSON.parse(data.join('\n'));
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid interpretation event.');
  const event = value as Record<string, unknown>;
  for (const key of ['chunk', 'notice', 'error']) {
    if (event[key] !== undefined && typeof event[key] !== 'string') throw new Error('Invalid interpretation event text.');
  }
  if (event.done !== undefined && typeof event.done !== 'boolean') throw new Error('Invalid interpretation completion event.');
  if (event.meta !== undefined) {
    const meta = event.meta as Record<string, unknown>;
    if (!meta || typeof meta !== 'object' || typeof meta.model !== 'string' || typeof meta.pipeline_type !== 'string') throw new Error('Invalid interpretation model metadata.');
  }
  return event as StreamEvent;
}

/** Network chunks are not event boundaries. Preserve split lines and UTF-8. */
export async function* readInterpretationEvents(response: Response, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error('The interpretation response has no readable stream.');
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let pending = '';
  let data: string[] = [];
  const cancel = () => { void reader.cancel().catch(() => undefined); };
  signal?.addEventListener('abort', cancel, { once: true });
  try {
    while (true) {
      signal?.throwIfAborted();
      const { value, done } = await reader.read();
      signal?.throwIfAborted();
      pending += done ? decoder.decode() : decoder.decode(value, { stream: true });
      if (done && pending) pending += '\n';
      let end: number;
      while ((end = pending.indexOf('\n')) !== -1) {
        const line = pending.slice(0, end).replace(/\r$/, '');
        pending = pending.slice(end + 1);
        if (!line) {
          const event = parseEvent(data); data = [];
          if (event) yield event;
        } else if (line.startsWith('data:')) {
          data.push(line.slice(5).replace(/^ /, ''));
        }
      }
      if (done) {
        const event = parseEvent(data);
        if (event) yield event;
        return;
      }
    }
  } finally {
    signal?.removeEventListener('abort', cancel);
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
