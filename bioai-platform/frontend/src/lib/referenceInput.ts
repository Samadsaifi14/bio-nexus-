function numeric(value: unknown): number | undefined {
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : undefined;
}

function parseDelimited(text: string): Record<string, unknown> {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) throw new Error('Delimited reference input needs a header and at least one data row.');
  const delimiter = lines[0].includes('\t') ? '\t' : ',';
  const headers = lines[0].split(delimiter).map(v => v.trim());
  const results = lines.slice(1).map(line => {
    const cells = line.split(delimiter);
    const row: Record<string, unknown> = {};
    headers.forEach((h, i) => {
      const raw = (cells[i] ?? '').trim();
      const n = Number(raw);
      row[h] = raw !== '' && Number.isFinite(n) ? n : raw;
    });
    return row;
  });
  return { results };
}

/** Normalize NCBI BLAST JSON2 into BioNexus' hit-level comparison contract. */
function normalizeNcbiBlastJson(payload: any): Record<string, unknown> | null {
  const output = payload?.BlastOutput2;
  if (!Array.isArray(output) || output.length === 0) return null;
  const search = output[0]?.report?.results?.search;
  if (!search || !Array.isArray(search.hits)) return null;
  const queryLength = numeric(search.query_len);
  const hits = search.hits.map((hit: any) => {
    const desc = Array.isArray(hit.description) ? hit.description[0] ?? {} : {};
    const hsps = Array.isArray(hit.hsps) ? hit.hsps : [];
    const best = hsps[0] ?? {};
    const alignLen = numeric(best.align_len);
    const identity = numeric(best.identity);
    const queryFrom = numeric(best.query_from);
    const queryTo = numeric(best.query_to);
    const querySpan = queryFrom !== undefined && queryTo !== undefined ? Math.abs(queryTo - queryFrom) + 1 : undefined;
    return {
      accession: desc.accession ?? desc.id ?? '',
      description: desc.title ?? '',
      organism: desc.sciname ?? undefined,
      evalue: numeric(best.evalue),
      identity_pct: identity !== undefined && alignLen ? (identity / alignLen) * 100 : undefined,
      query_coverage_pct: querySpan !== undefined && queryLength ? (querySpan / queryLength) * 100 : undefined,
      bit_score: numeric(best.bit_score),
      alignment_length: alignLen,
      query_from: queryFrom,
      query_to: queryTo,
      hit_from: numeric(best.hit_from),
      hit_to: numeric(best.hit_to),
      gaps: numeric(best.gaps),
      query_alignment: best.qseq,
      hit_alignment: best.hseq,
      midline: best.midline,
    };
  });
  return { hits, database: search.search_target?.db, query_length: queryLength, source_format: 'NCBI BLAST JSON2' };
}

export function parseReferenceInput(analysisType: string, text: string): Record<string, unknown> {
  const trimmed = text.trim();
  if (!trimmed) throw new Error('Paste or upload a reference result first.');

  if (analysisType === 'msa' && trimmed.startsWith('>')) {
    return { aln_fasta: trimmed, source_format: 'aligned FASTA' };
  }
  if (analysisType === 'phylo' && trimmed.startsWith('(')) {
    return { newick: trimmed, source_format: 'Newick' };
  }

  try {
    const parsed = JSON.parse(trimmed);
    if (analysisType === 'blast') {
      const ncbi = normalizeNcbiBlastJson(parsed);
      if (ncbi) return ncbi;
    }
    if (Array.isArray(parsed)) return { results: parsed };
    if (parsed && typeof parsed === 'object') return parsed as Record<string, unknown>;
  } catch {
    // Continue to text/tabular formats.
  }

  if (trimmed.includes('\t') || (trimmed.includes(',') && trimmed.includes('\n'))) {
    return parseDelimited(trimmed);
  }

  throw new Error('Unsupported reference format. Use JSON, TSV/CSV, aligned FASTA for MSA, or Newick for phylogeny. NCBI BLAST JSON2 is accepted directly.');
}
