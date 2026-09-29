import type { GeoRecord } from './api';

export type GeoCountColumn = {
  name: string;
  sample: string;
  title: string;
  condition: string;
};

export type GeoCountPreview = {
  filename: string;
  source: string;
  genes: number;
  columns: GeoCountColumn[];
  excludedColumns: string[];
  counts: File;
};

const MAX_DECOMPRESSED = 60 * 1024 * 1024;

function fields(line: string, delimiter: string): string[] {
  const output: string[] = [];
  let cell = '';
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const character = line[i];
    if (character === '"') {
      if (quoted && line[i + 1] === '"') { cell += '"'; i++; }
      else quoted = !quoted;
    } else if (character === delimiter && !quoted) {
      output.push(cell.trim()); cell = '';
    } else cell += character;
  }
  if (quoted) throw new Error('The count matrix contains an unsupported multiline quoted field.');
  output.push(cell.trim());
  return output;
}

function matchSample(header: string, record: GeoRecord): { sample: string; title: string; condition: string } {
  const compact = (value: string) => value.toUpperCase().replace(/[^A-Z0-9]/g, '');
  const candidate = compact(header);
  const matched = record.samples.filter(item => {
    if (candidate.includes(item.accession)) return true;
    const library = item.title.match(/\b[A-Z]{1,6}\d{5,}\b/gi)?.at(-1);
    return Boolean(library && candidate.includes(compact(library)));
  });
  if (matched.length !== 1) return { sample: '', title: '', condition: '' };
  const title = matched[0].title;
  const groups = title.match(/\b(sensitive|resistant|control|treated|healthy|disease)\b/gi) ?? [];
  return { sample: matched[0].accession, title, condition: groups.length === 1 ? groups[0].toLowerCase() : '' };
}

async function decodeMatrix(blob: Blob, gzip: boolean): Promise<string> {
  const stream = gzip ? blob.stream().pipeThrough(new DecompressionStream('gzip')) : blob.stream();
  const reader = stream.getReader();
  const parts: Uint8Array[] = [];
  let size = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_DECOMPRESSED) { await reader.cancel(); throw new Error('The unpacked count matrix exceeds the 60 MB analysis limit.'); }
    parts.push(value);
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const part of parts) { bytes.set(part, offset); offset += part.byteLength; }
  return new TextDecoder('utf-8', { fatal: true }).decode(bytes).replace(/^\uFEFF/, '');
}

export async function prepareGeoCounts(record: GeoRecord, filename: string): Promise<GeoCountPreview> {
  const response = await fetch(`/api/geo/${record.accession}/counts?file=${encodeURIComponent(filename)}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || 'The published count matrix could not be retrieved.');
  }
  const raw = await decodeMatrix(await response.blob(), filename.toLowerCase().endsWith('.gz'));
  const lines = raw.split(/\r?\n/).filter(line => line.trim() && !line.startsWith('#'));
  if (lines.length < 3) throw new Error('The published matrix has too few gene rows for analysis.');
  const delimiter = lines[0].includes('\t') ? '\t' : ',';
  const heading = fields(lines[0], delimiter);
  if (heading.length < 3 || new Set(heading).size !== heading.length) throw new Error('The matrix needs unique sample columns and a gene column.');
  const rows = lines.slice(1).map((line, index) => {
    const values = fields(line, delimiter);
    if (values.length !== heading.length) throw new Error(`Matrix row ${index + 2} has ${values.length} fields; expected ${heading.length}.`);
    return values;
  });
  const annotation = /^(gene_?name|gene_?symbol|symbol|description|gene_?type|gene_?biotype|biotype|chr|chromosome|start|end|strand|length|gene_?length|entrez|ensembl_?id)$/i;
  const invalid = (column: number) => rows.findIndex(row => !/^\d+$/.test(row[column]));
  const selected = heading.slice(1).map((name, index) => index + 1).filter(index =>
    !annotation.test(heading[index]) && (matchSample(heading[index], record).sample || invalid(index) === -1));
  if (selected.length < 2) {
    const index = heading.slice(1).findIndex((name, column) => !annotation.test(name) && invalid(column + 1) >= 0) + 1;
    if (index > 0) {
      const row = invalid(index);
      throw new Error(`No usable raw count matrix: row ${row + 2}, column “${heading[index]}” contains “${rows[row][index].slice(0, 60)}”. DESeq2 requires non-negative integer counts.`);
    }
    throw new Error('This file has fewer than two sample count columns.');
  }
  const bad = selected.map(index => ({ index, row: invalid(index) })).find(item => item.row >= 0);
  if (bad) throw new Error(`Row ${bad.row + 2}, column “${heading[bad.index]}” contains “${rows[bad.row][bad.index].slice(0, 60)}”. DESeq2 requires raw non-negative integer counts.`);
  const names = selected.map(index => heading[index]);
  const columns: GeoCountColumn[] = names.map(name => ({ name, ...matchSample(name, record) }));
  const excludedColumns = heading.slice(1).filter((_, index) => !selected.includes(index + 1));
  const ids = new Set<string>();
  const output = [`gene\t${names.join('\t')}`];
  for (const values of rows) {
    const gene = values[0].trim();
    if (!gene || ids.has(gene)) throw new Error('The count matrix has empty or duplicate gene identifiers.');
    ids.add(gene);
    output.push(`${gene}\t${selected.map(index => values[index]).join('\t')}`);
  }
  const tsv = output.join('\n') + '\n';
  if (new Blob([tsv]).size > MAX_DECOMPRESSED) throw new Error('The converted matrix exceeds the 60 MB analysis limit.');
  return {
    filename, source: `https://ftp.ncbi.nlm.nih.gov/geo/series/GSE${record.accession.slice(3, -3)}nnn/${record.accession}/suppl/${encodeURIComponent(filename)}`,
    genes: ids.size, columns, excludedColumns,
    counts: new File([tsv], `${record.accession}_${filename.replace(/\.(gz)$/i, '').replace(/\.(csv|txt)$/i, '.tsv')}`, { type: 'text/tab-separated-values' }),
  };
}
