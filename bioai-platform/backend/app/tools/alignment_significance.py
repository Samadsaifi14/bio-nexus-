"""Composition-preserving Monte Carlo score test; not homology probability."""
import hashlib
import math
import random
from statistics import mean, pstdev
import Bio
from Bio.Align import PairwiseAligner, substitution_matrices
from app.tools.pairwise_alignment import PairwiseAlignError, MATRICES, _normalize_sequence


def alignment_score_test(seq_a, seq_b, *, mode='global', matrix='blosum62',
                         open_gap_score=-10, extend_gap_score=-1, permutations=199, seed=2026):
    a, b = _normalize_sequence(seq_a, 'query'), _normalize_sequence(seq_b, 'subject')
    if type(permutations) is not int or not 19 <= permutations <= 999:
        raise PairwiseAlignError('Permutation score tests need 19–999 permutations')
    if type(seed) is not int or not 0 <= seed <= 2**32-1:
        raise PairwiseAlignError('Random seed must be an unsigned 32-bit integer')
    if len(a) * len(b) * permutations > 50_000_000:
        raise PairwiseAlignError('Requested score test exceeds the computation budget; shorten the sequences or reduce permutations')
    if mode not in {'global', 'local'} or matrix not in MATRICES:
        raise PairwiseAlignError('Unsupported score-test mode or matrix')
    if not all(math.isfinite(v) and v <= 0 for v in (open_gap_score, extend_gap_score)):
        raise PairwiseAlignError('Gap penalties must be finite and non-positive')
    substitution = substitution_matrices.load(MATRICES[matrix])
    if (set(a) | set(b)) - (set(substitution.alphabet) - {'*'}):
        raise PairwiseAlignError('Sequence contains residues unsupported by the selected matrix')
    aligner = PairwiseAligner()
    aligner.mode = mode; aligner.substitution_matrix = substitution
    aligner.open_gap_score = open_gap_score; aligner.extend_gap_score = extend_gap_score
    observed = float(aligner.score(a, b))
    rng = random.Random(seed)
    scores = []
    for _ in range(permutations):
        residues = list(b)
        rng.shuffle(residues)
        scores.append(float(aligner.score(a, ''.join(residues))))
    exceedances = sum(value >= observed for value in scores)
    return {'method': 'composition-preserving subject-shuffle score test',
            'observed_score': observed, 'p_value': (exceedances + 1) / (permutations + 1),
            'exceedances': exceedances, 'permutations': permutations, 'seed': seed,
            'p_value_resolution': 1 / (permutations + 1), 'null_score_mean': mean(scores),
            'null_score_std': pstdev(scores), 'null_scores': scores,
            'parameters': {'mode': mode, 'matrix': matrix, 'open_gap_score': open_gap_score, 'extend_gap_score': extend_gap_score},
            'provenance': {'biopython_version': Bio.__version__,
                           'query_sha256': hashlib.sha256(a.encode()).hexdigest(),
                           'subject_sha256': hashlib.sha256(b.encode()).hexdigest(),
                           'p_value_method_doi': '10.2202/1544-6115.1585'},
            'interpretation': 'Exploratory single-comparison score test under exchangeable subject residues. Preserves monoresidue composition, not sequence motifs or phylogenetic dependence. No multiple-testing correction; not a BLAST E-value or probability of homology.'}
