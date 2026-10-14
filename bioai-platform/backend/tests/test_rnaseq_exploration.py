import csv
import hashlib
import json
import os
import shutil
import zipfile

import numpy as np
import pytest

from app.rnaseq.expression import ExpressionParameters, _run_r, methods_text, write_reproducibility_bundle
from app.rnaseq.enrichment_retry import EnrichmentOptions


def test_qc_methods_do_not_claim_inference_and_bundle_preserves_input_bytes(tmp_path):
    counts = tmp_path / 'counts.tsv'; counts.write_bytes(b'gene\ts1\ts2\ng1\t1\t2\n')
    metadata = tmp_path / 'metadata.tsv'; metadata.write_bytes(b'sample\tcondition\ns1\ta\ns2\tb\n')
    out = tmp_path / 'results'; out.mkdir()
    provenance = {'run_id': 'test-run', 'counts_sha256': hashlib.sha256(counts.read_bytes()).hexdigest(),
                  'metadata_sha256': hashlib.sha256(metadata.read_bytes()).hexdigest(), 'min_count': 10, 'min_samples': 0}
    summary = {'min_samples': 2, 'design': '~ condition', 'vst_method': 'varianceStabilizingTransformation'}
    text = methods_text(provenance, summary, 'qc')
    assert 'at least 2 samples' in text and 'testing was not performed' in text
    assert 'Wald test compared' not in text
    (out / 'methods.txt').write_text(text)
    write_reproducibility_bundle(out, counts, metadata, provenance)
    with zipfile.ZipFile(out / 'reproducibility_bundle.zip') as archive:
        assert archive.read('inputs/counts.tsv') == counts.read_bytes()
        assert archive.read('inputs/metadata.tsv') == metadata.read_bytes()
        index = json.loads(archive.read('artifact_index.json'))
        for name, entry in index['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == entry['sha256']


def test_salmon_bundle_contains_quantifications_and_portable_manifest(tmp_path):
    quant = tmp_path / 'quant.sf'; quant.write_text('Name\tNumReads\nt1\t1.5\n')
    counts = tmp_path / 'manifest.tsv'; counts.write_text(f'sample\tquant_file\ns1\t{quant}\n')
    metadata = tmp_path / 'metadata.tsv'; metadata.write_text('sample\tcondition\ns1\ta\n')
    mapping = tmp_path / 'tx2gene.tsv'; mapping.write_text('transcript\tgene\nt1\tg1\n')
    out = tmp_path / 'out'; out.mkdir()
    write_reproducibility_bundle(out, counts, metadata, {'run_id': 'salmon-run', 'input_kind': 'salmon'}, mapping)
    with zipfile.ZipFile(out / 'reproducibility_bundle.zip') as archive:
        row = next(csv.DictReader(archive.read('portable_quant_manifest.tsv').decode().splitlines(), delimiter='\t'))
        assert row['sample'] == 's1' and archive.read(row['quant_file']) == quant.read_bytes()
        assert archive.read('inputs/tx2gene.tsv') == mapping.read_bytes()


def test_gsea_is_an_explicit_supported_method():
    EnrichmentOptions(method='gsea').validate()


@pytest.mark.skipif(not shutil.which(os.environ.get('BIONEXUS_RSCRIPT', 'Rscript')), reason='R runtime absent')
def test_large_low_abundance_matrix_uses_exact_vst_and_exports_batch_metadata(tmp_path):
    values = np.random.default_rng(623).negative_binomial(2, .5, size=(1200, 8))
    counts = tmp_path / 'counts.tsv'
    with counts.open('w') as handle:
        writer = csv.writer(handle, delimiter='\t')
        writer.writerow(['gene', *[f's{i}' for i in range(8)]])
        writer.writerows([f'g{i}', *row] for i, row in enumerate(values))
    metadata = tmp_path / 'metadata.tsv'
    metadata.write_text('sample\tcondition\tbatch\n' + ''.join(f's{i}\t{"a" if i < 4 else "b"}\t{"x" if i % 2 else "y"}\n' for i in range(8)))
    out = tmp_path / 'out'; out.mkdir()
    summary = _run_r(counts, metadata, out, ExpressionParameters(reference_level='a', test_level='b',
        min_count=1, min_samples=2, covariates=('batch',)), stage='qc', checkpoint_path=tmp_path / 'qc.rds')
    assert summary['genes_kept'] >= 1000
    assert summary['vst_method'] == 'varianceStabilizingTransformation'
    with (out / 'pca_coordinates.tsv').open() as handle:
        rows = list(csv.DictReader(handle, delimiter='\t'))
    assert len(rows) == 8 and {row['batch'] for row in rows} == {'x', 'y'}
    assert not (out / 'deseq2_all_results.tsv').exists()
