"""Real bounded DIAMOND protein search against a caller-supplied FASTA database."""
from __future__ import annotations
import hashlib
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

MAX_DATABASE_BYTES = 5 * 1024 * 1024
MAX_DATABASE_RESIDUES = 1_000_000
_SLOTS = threading.BoundedSemaphore(2)
_PROTEIN = set('ACDEFGHIKLMNPQRSTVWYBXZJUO')

class SimilarityError(ValueError):
    pass

class EngineUnavailable(RuntimeError):
    pass


def parse_protein_fasta(text: str, *, max_records: int = 5000) -> list[dict]:
    if len(text.encode('utf-8')) > MAX_DATABASE_BYTES:
        raise SimilarityError('Protein FASTA exceeds the 5 MB limit')
    records = []
    identifier = None
    description = ''
    sequence = []
    seen = set()
    def finish():
        if identifier is None:
            return
        seq = ''.join(sequence).upper()
        if not 10 <= len(seq) <= 10000 or not set(seq) <= _PROTEIN:
            raise SimilarityError('Each protein must contain 10–10,000 valid amino-acid residues; gaps and stops are not accepted')
        records.append({'id': identifier, 'description': description, 'sequence': seq})
        if len(records) > max_records:
            raise SimilarityError(f'Protein FASTA is limited to {max_records} records')
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('>'):
            finish()
            header = line[1:].strip()
            if not header:
                raise SimilarityError('Every FASTA record needs a nonempty identifier')
            identifier = header.split()[0]
            if not re.fullmatch(r'[A-Za-z0-9_.|:-]{1,120}', identifier) or identifier in seen:
                raise SimilarityError('FASTA identifiers must be unique and contain only letters, numbers, dots, pipes, colons, dashes or underscores')
            seen.add(identifier)
            description = header[:1000]
            sequence = []
        else:
            if identifier is None:
                raise SimilarityError('Provide protein FASTA records with >identifier headers')
            sequence.append(''.join(line.split()))
    finish()
    if not records or sum(len(r['sequence']) for r in records) > MAX_DATABASE_RESIDUES:
        raise SimilarityError('Reference FASTA must contain 1–5,000 proteins and at most 1,000,000 residues')
    return records


def normalize(records: list[dict]) -> str:
    return ''.join(f">{r['id']}\n{r['sequence']}\n" for r in records)


def parse_hits(text: str, references: dict[str, dict], query_length: int) -> list[dict]:
    hits = []
    for line in text.splitlines():
        fields = line.split('\t')
        if len(fields) != 10 or fields[0] not in references:
            raise SimilarityError('DIAMOND returned an invalid alignment record')
        identifier, identity, length, qstart, qend, sstart, send, evalue, bitscore, qcov = fields
        try:
            nums = [float(identity), float(evalue), float(bitscore), float(qcov)]
            coordinates = [int(x) for x in (length, qstart, qend, sstart, send)]
        except ValueError as exc:
            raise SimilarityError('DIAMOND returned invalid numeric evidence') from exc
        aln_length, qfrom, qto, hfrom, hto = coordinates
        if (not all(math.isfinite(x) for x in nums) or not 0 <= nums[0] <= 100
                or nums[1] < 0 or nums[2] < 0 or not 0 <= nums[3] <= 100 or aln_length < 1
                or not 1 <= qfrom <= qto <= query_length
                or not 1 <= hfrom <= hto <= len(references[identifier]['sequence'])):
            raise SimilarityError('DIAMOND alignment evidence is outside valid bounds')
        hits.append({'accession': identifier, 'description': references[identifier]['description'],
                     'identity_pct': nums[0], 'alignment_length': aln_length,
                     'query_from': qfrom, 'query_to': qto, 'hit_from': hfrom, 'hit_to': hto,
                     'evalue': nums[1], 'evalue_raw': evalue, 'bit_score': nums[2],
                     'query_coverage_pct': nums[3]})
    return hits


def search(query_fasta: str, reference_fasta: str, max_hits: int = 20) -> dict:
    query = parse_protein_fasta(query_fasta, max_records=1)
    references = parse_protein_fasta(reference_fasta)
    if type(max_hits) is not int or not 1 <= max_hits <= 100:
        raise SimilarityError('max_hits must be between 1 and 100')
    executable = shutil.which(os.environ.get('BIONEXUS_DIAMOND', 'diamond'))
    if not executable:
        raise EngineUnavailable('DIAMOND is not installed; custom database search is unavailable')
    if not _SLOTS.acquire(blocking=False):
        raise EngineUnavailable('Local similarity workers are busy; retry after the running searches finish')
    try:
        version = subprocess.run([executable, 'version'], capture_output=True, text=True, timeout=10, check=True).stdout.strip()
        with tempfile.TemporaryDirectory(prefix='bionexus-diamond-') as folder:
            root = Path(folder)
            query_path, ref_path, output = root / 'query.faa', root / 'reference.faa', root / 'hits.tsv'
            qbody, rbody = normalize(query), normalize(references)
            query_path.write_text(qbody); ref_path.write_text(rbody)
            commands = [
                [executable, 'makedb', '--in', str(ref_path), '--db', str(root / 'reference'), '--threads', '2', '--no-parse-seqids'],
                [executable, 'blastp', '--query', str(query_path), '--db', str(root / 'reference'),
                 '--out', str(output), '--outfmt', '6', 'sseqid', 'pident', 'length', 'qstart', 'qend',
                 'sstart', 'send', 'evalue', 'bitscore', 'qcovhsp', '--very-sensitive', '--threads', '2',
                 '--max-target-seqs', str(max_hits), '--evalue', '0.001', '--block-size', '0.1', '--index-chunks', '4'],
            ]
            for command, timeout in zip(commands, (60, 120)):
                completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout, check=False)
                if completed.returncode != 0:
                    raise EngineUnavailable('DIAMOND execution failed; no biological no-hit result is inferred')
            if not output.is_file():
                raise EngineUnavailable('DIAMOND did not produce its result file')
            raw = output.read_text()
            lookup = {r['id']: r for r in references}
            hits = parse_hits(raw, lookup, len(query[0]['sequence']))
            digest = lambda data: hashlib.sha256(data).hexdigest()
            return {'status': 'SUCCEEDED', 'engine': 'DIAMOND', 'engine_version': version,
                    'inputs': {'query_fasta': qbody, 'reference_fasta': rbody},
                    'source': 'DIAMOND · uploaded protein FASTA', 'search_complete': True,
                    'hits': hits, 'count': len(hits), 'reference_records': len(references),
                    'parameters': {'program': 'blastp', 'sensitivity': 'very-sensitive', 'evalue': 0.001,
                                   'max_target_sequences': max_hits, 'threads': 2, 'coordinates': '1-based inclusive'},
                    'provenance': {'query_sha256': digest(qbody.encode()), 'reference_sha256': digest(rbody.encode()),
                                   'submitted_query_sha256': digest(query_fasta.encode()),
                                   'submitted_reference_sha256': digest(reference_fasta.encode()),
                                   'engine_sha256': digest(Path(executable).read_bytes()), 'output_sha256': digest(raw.encode()),
                                   'method_doi': '10.1038/s41592-021-01101-x', 'reference_identity': 'user-supplied; taxonomy not independently verified'},
                    'claim': 'Real DIAMOND protein alignment against the supplied reference only; not an NCBI BLAST search or a function/affinity prediction.'}
    except subprocess.TimeoutExpired as exc:
        raise EngineUnavailable('DIAMOND exceeded the execution limit; no biological no-hit result is inferred') from exc
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EngineUnavailable('DIAMOND could not execute in this runtime') from exc
    finally:
        _SLOTS.release()
