import csv
import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "benchmark/fixtures/rnaseq/full_matrix"
spec = importlib.util.spec_from_file_location("full_matrix_regression", FIXTURE / "run_regression.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_complete_supplied_fixture_is_unmodified_and_metadata_aligned():
    payload = (FIXTURE / "counts.tsv").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == "b7a9736672a6cebfdeea78dd151f5c764b058537cac09aeb0256cbfb7123dc08"
    rows = list(csv.reader(payload.decode().splitlines(), delimiter="\t"))
    assert len(rows) == 22086 and len(rows[0]) == 19
    assert all(len(row) == 19 and all(value.isdigit() for value in row[1:]) for row in rows[1:])
    with (FIXTURE / "metadata.tsv").open() as handle:
        metadata = list(csv.DictReader(handle, delimiter="\t"))
    assert [row["sample"] for row in metadata] == rows[0][1:]


@pytest.mark.parametrize("observed", ["g1\t1.01\n", "g1\t\n", "g2\t1\n", "g1\t1\ng1\t1\n"])
def test_parity_gate_rejects_changed_values_missingness_identity_or_duplicates(tmp_path, observed):
    reference, actual = tmp_path / "reference.tsv", tmp_path / "actual.tsv"
    reference.write_text("gene\tvalue\ng1\t1\n")
    actual.write_text("gene\tvalue\n" + observed)
    with pytest.raises(AssertionError):
        runner.compare_tables(reference, actual, "gene", ["value"])
