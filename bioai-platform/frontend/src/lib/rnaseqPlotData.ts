import type { RnaSeqArtifact } from './rnaseqExpressionApi';

export type PlotRow = Record<string, string>;
export type EvidencePoint = { id: string; x: number; y: number; group: string; row: PlotRow };

export function parsePlotTsv(text: string): PlotRow[] {
  const lines = text.replace(/^\uFEFF/, '').trimEnd().split(/\r?\n/);
  const headers = lines.shift()?.split('\t') ?? [];
  if (!headers.length || headers.some(h => !h) || new Set(headers).size !== headers.length) throw new Error('Invalid plot table header.');
  return lines.filter(Boolean).map(line => {
    const cells = line.split('\t');
    if (cells.length !== headers.length) throw new Error('Plot table has an inconsistent column count.');
    return Object.fromEntries(headers.map((name, index) => [name, cells[index]]));
  });
}

function numeric(value: string | undefined): number | null {
  if (value === undefined || !value.trim() || ['NA', 'NaN'].includes(value)) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function evidencePoints(rows: PlotRow[], kind: 'pca' | 'volcano', groupKey: string): { points: EvidencePoint[]; excluded: number } {
  const seen = new Set<string>();
  let excluded = 0;
  const points: EvidencePoint[] = [];
  for (const row of rows) {
    const id = row[kind === 'pca' ? 'sample' : 'gene'];
    if (!id || seen.has(id)) throw new Error('Missing or duplicate plot identifiers.');
    seen.add(id);
    const x = numeric(row[kind === 'pca' ? 'PC1' : 'log2FoldChange']);
    const y = numeric(row[kind === 'pca' ? 'PC2' : 'minus_log10_padj']);
    const padj = kind === 'volcano' ? numeric(row.padj) : null;
    if (x === null || y === null || (kind === 'volcano' && (padj === null || padj < 0 || padj > 1 || y < 0))) { excluded++; continue; }
    points.push({ id, x, y, group: row[groupKey] || 'Not declared', row });
  }
  return { points, excluded };
}

export async function loadPlotEvidence(item: RnaSeqArtifact, signal: AbortSignal): Promise<PlotRow[]> {
  if (!Number.isSafeInteger(item.bytes) || item.bytes < 1 || item.bytes > 60 * 1024 * 1024) throw new Error('Plot evidence exceeds the 60 MB viewer limit. Download the original TSV.');
  const response = await fetch(item.url, { signal });
  if (!response.ok) throw new Error(`Plot evidence request failed (${response.status}).`);
  const reader = response.body?.getReader();
  if (!reader) throw new Error('Plot evidence streaming is unavailable. Download the original TSV.');
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > item.bytes) throw new Error('Plot evidence byte count differs from its manifest.');
      chunks.push(value);
    }
  } finally { await reader.cancel().catch(() => undefined); }
  if (size !== item.bytes) throw new Error('Plot evidence is incomplete.');
  const buffer = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { buffer.set(chunk, offset); offset += chunk.byteLength; }
  const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', buffer)), value => value.toString(16).padStart(2, '0')).join('');
  if (hash !== item.sha256.toLowerCase()) throw new Error('Plot evidence checksum mismatch.');
  return parsePlotTsv(new TextDecoder('utf-8', { fatal: true }).decode(buffer));
}
