from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import ngs_demo


def _client():
    app = FastAPI()
    app.include_router(ngs_demo.router)
    return TestClient(app)


def test_demo_catalog_exposes_runnable_paired_fastq_sets():
    client = _client()
    response = client.get('/api/ngs/v2/demos/catalog')
    assert response.status_code == 200
    demos = response.json()['demos']
    ids = {item['id'] for item in demos}
    assert {'wgs-truth-control', 'wgs-clean', 'wgs-mixed-quality', 'wes-small'} <= ids
    truth = next(item for item in demos if item['id'] == 'wgs-truth-control')
    assert truth['paired_end'] is True
    assert truth['read_length'] == 150
    assert truth['truth_bearing'] is True
    assert set(truth['downloads']) == {'r1', 'r2', 'reference'}


def test_downloaded_truth_fastqs_and_reference_are_well_formed():
    client = _client()
    r1 = client.get('/api/ngs/v2/demos/wgs-truth-control/download/r1')
    r2 = client.get('/api/ngs/v2/demos/wgs-truth-control/download/r2')
    reference = client.get('/api/ngs/v2/demos/wgs-truth-control/download/reference')

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert reference.status_code == 200
    assert 'attachment;' in r1.headers['content-disposition']
    assert 'attachment;' in r2.headers['content-disposition']
    assert 'attachment;' in reference.headers['content-disposition']

    r1_lines = [line for line in r1.text.splitlines() if line]
    r2_lines = [line for line in r2.text.splitlines() if line]
    assert len(r1_lines) % 4 == 0
    assert len(r2_lines) % 4 == 0
    assert r1_lines[0].startswith('@BNTRUTH:')
    assert r2_lines[0].startswith('@BNTRUTH:')
    assert reference.text.startswith('>chrSynthetic')


def test_unknown_demo_file_fails_closed():
    client = _client()
    assert client.get('/api/ngs/v2/demos/not-a-demo/download/r1').status_code == 404
    assert client.get('/api/ngs/v2/demos/wgs-clean/download/reference').status_code == 404
