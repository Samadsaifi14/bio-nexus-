"""Independent deterministic aligned-FASTA column filtering (not realignment)."""
from hashlib import sha256
from math import isfinite

ALPHABETS = {'dna': set('ACGT-'), 'rna': set('ACGU-'), 'protein': set('ACDEFGHIKLMNPQRSTVWY-')}


def trim_alignment(fasta: str, molecule: str = 'protein', mode: str = 'all_gap', gap_percent: float = 50) -> dict:
    if molecule not in ALPHABETS or mode not in {'all_gap', 'any_gap', 'gap_percent'}:
        raise ValueError('Choose dna/rna/protein and all_gap/any_gap/gap_percent')
    if not isfinite(gap_percent) or not 0 < gap_percent <= 100:
        raise ValueError('Gap percentage must be greater than 0 and at most 100')
    if len(fasta) > 2_000_000:
        raise ValueError('Aligned FASTA exceeds 2 million characters')
    records: list[tuple[str, str]] = []
    header = None
    parts: list[str] = []
    for line in fasta.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('>'):
            if header is not None:
                records.append((header, ''.join(parts)))
            header, parts = line[1:].strip(), []
            if not header or len(header) > 200 or any(ord(c) < 32 for c in header):
                raise ValueError('FASTA headers must be nonempty and at most 200 characters')
        else:
            if header is None:
                raise ValueError('Aligned FASTA must begin with a header')
            seq = line.upper()
            if set(seq) - ALPHABETS[molecule]:
                raise ValueError(f'Invalid {molecule} characters; use canonical residues and hyphen gaps')
            parts.append(seq)
    if header is not None:
        records.append((header, ''.join(parts)))
    if not 2 <= len(records) <= 1000:
        raise ValueError('Provide 2–1000 aligned records')
    ids = [h.split()[0] for h, _ in records]
    if len(set(ids)) != len(ids):
        raise ValueError('FASTA identifiers must be unique')
    width = len(records[0][1])
    if not width or any(len(s) != width for _, s in records):
        raise ValueError('Aligned records must have equal nonzero widths')
    gaps = [sum(s[c] == '-' for _, s in records) for c in range(width)]
    dropped = [c for c, n in enumerate(gaps) if (n == len(records) if mode == 'all_gap' else n > 0 if mode == 'any_gap' else 100 * n >= gap_percent * len(records))]
    dropped_set = set(dropped)
    kept = [c for c in range(width) if c not in dropped_set]
    if not kept:
        raise ValueError('Filtering would remove every column; choose a less aggressive policy')
    output = ''.join(f'>{h}\n' + ''.join(s[c] for c in kept) + '\n' for h, s in records)
    removed = sum(len(records) - gaps[c] for c in dropped)
    return {'trimmed_fasta': output, 'mask': {
        'coordinate_convention': '1-based input alignment columns; kept list maps output positions to input positions',
        'kept_columns': [c + 1 for c in kept], 'dropped_columns': [c + 1 for c in dropped],
        'input_width': width, 'output_width': len(kept), 'record_count': len(records),
        'molecule': molecule, 'mode': mode, 'gap_percent': gap_percent if mode == 'gap_percent' else None,
        'residues_removed': removed, 'input_sha256': sha256(fasta.encode()).hexdigest(),
        'output_sha256': sha256(output.encode()).hexdigest(),
    }, 'warning': 'Filtering deletes residues in partially gapped columns and can change downstream inference.' if mode != 'all_gap' else 'Only all-gap columns are removed; ungapped sequences are preserved.'}
