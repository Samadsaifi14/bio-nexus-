import type { SequenceType } from '@/types/pipeline';

export const PROTEIN_CODES = new Set('ACDEFGHIKLMNPQRSTVWYUBZXOJ');

/**
 * Strip FASTA headers and whitespace, returning only the raw sequence characters.
 */
export function stripFastaHeader(text: string): string {
  return text.split('\n').filter(l => !l.startsWith('>')).join('\n');
}

/**
 * Remove everything except alphabetic characters and uppercase the result.
 */
export function cleanSequence(text: string): string {
  return text.replace(/[^A-Za-z]/g, '').toUpperCase();
}

/**
 * Parse FASTA text into an array of { id, sequence } objects.
 * Handles multi-line sequences, semicolon comments, and whitespace.
 */
export function parseFasta(raw: string): Array<{ id: string; sequence: string }> {
  const seqs: Array<{ id: string; sequence: string }> = [];
  let cur: { id: string; seq: string[] } | null = null;
  for (const line of raw.split('\n')) {
    const t = line.trim();
    if (t.startsWith('>')) {
      if (cur) seqs.push({ id: cur.id, sequence: cur.seq.join('') });
      cur = { id: t.slice(1).split(/\s+/)[0] || 'Seq', seq: [] };
    } else if (cur && t && !t.startsWith(';')) {
      cur.seq.push(t);
    }
  }
  if (cur) seqs.push({ id: cur.id, sequence: cur.seq.join('') });
  return seqs;
}

/**
 * Detect whether a raw input (possibly with FASTA headers) is protein, DNA, RNA, or unknown.
 */
export function detectSequenceType(seq: string): SequenceType {
  const body = stripFastaHeader(seq);
  const clean = cleanSequence(body);
  if (!clean) return 'unknown';
  const seqSet = new Set(clean);
  const nonProtein = Array.from(seqSet).filter(c => !PROTEIN_CODES.has(c));
  if (nonProtein.length === 0) return 'protein';
  const inNucleic = nonProtein.every(c => 'ACGUTN'.includes(c));
  if (inNucleic && seqSet.has('U') && !seqSet.has('T')) return 'rna';
  if (inNucleic && Array.from(seqSet).every(c => 'ACGTN'.includes(c))) return 'dna';
  if (nonProtein.every(c => 'ACGUTN'.includes(c))) return 'rna';
  return 'unknown';
}

/**
 * Validate that FASTA text contains at least 2 distinct sequences of sufficient length.
 * Returns null if valid, or an error message string.
 */
export function validateFasta(text: string): string | null {
  if (!text.trim()) return 'Enter sequences in FASTA format';
  const seqs = parseFasta(text);
  if (seqs.length < 2) return 'Provide at least 2 sequences in FASTA format (each starting with >)';
  const uniqueSeqs = new Set(seqs.map(s => s.sequence.toUpperCase()));
  if (uniqueSeqs.size < 2) return 'Sequences are identical — provide different sequences for alignment';
  for (const s of seqs) {
    if (s.sequence.length < 4) return `Sequence "${s.id}" is too short (min 4 residues)`;
  }
  return null;
}
