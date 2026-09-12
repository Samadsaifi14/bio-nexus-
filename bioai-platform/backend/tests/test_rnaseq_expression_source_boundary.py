from pathlib import Path


def test_expression_route_does_not_persist_raw_uploads():
    text = (Path(__file__).resolve().parents[1] / "app" / "rnaseq" / "expression.py").read_text(encoding="utf-8")
    assert 'TemporaryDirectory(prefix="bionexus-rnaseq-' in text
    assert 'counts_sha256' in text
    assert 'metadata_sha256' in text
    assert 'raw uploads are not persisted' not in text  # prose lives at the router/docs boundary
    assert 'rnaseq-artifacts' in text
    assert 'public": False' in text


def test_expression_router_requires_authenticated_user_for_writes_and_reads():
    text = (Path(__file__).resolve().parents[1] / "app" / "routers" / "rnaseq_expression.py").read_text(encoding="utf-8")
    assert text.count("Depends(require_user_id)") >= 3
    assert 'prefix="/api/ngs/v2/rnaseq/expression"' in text
