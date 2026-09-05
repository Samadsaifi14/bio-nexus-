from app.models.responses import NgsRnaSeqProductionPlanRequest
from app.ngs.orchestrator import build_dag
from app.ngs.rnaseq_production import RNASEQ_RELEASE, build_rnaseq_production_plan


def _request(**overrides):
    base = dict(samplesheet_path="samples.csv", outdir="/tmp/rnaseq", genome="GRCh38", execution_profile="docker", aligner="star_salmon")
    base.update(overrides)
    return NgsRnaSeqProductionPlanRequest(**base)


def test_rnaseq_plan_is_pinned_and_uses_argv_not_shell_string():
    plan = build_rnaseq_production_plan(_request())
    assert plan["ready_to_launch"] is True
    assert plan["workflow"]["name"] == "nf-core/rnaseq"
    assert plan["workflow"]["revision"] == RNASEQ_RELEASE == "3.26.0"
    argv = plan["command_argv"]
    assert argv[:4] == ["nextflow", "run", "nf-core/rnaseq", "-r"]
    assert "--aligner" in argv and "star_salmon" in argv
    assert {a["id"] for a in plan["required_artifacts"]} >= {"fastqc", "multiqc", "alignment", "quantification", "provenance"}


def test_custom_reference_requires_fasta_and_gtf_together():
    plan = build_rnaseq_production_plan(_request(genome=None, fasta="ref.fa", gtf=None))
    assert plan["ready_to_launch"] is False
    assert any("FASTA and GTF together" in blocker for blocker in plan["blockers"])


def test_hisat2_without_salmon_does_not_claim_quantification():
    plan = build_rnaseq_production_plan(_request(aligner="hisat2", pseudo_aligner=None))
    assert plan["workflow"]["quantification_expected"] == "false"
    assert any("does not use that route for expression quantification" in warning for warning in plan["warnings"])


def test_de_and_fusion_are_separate_evidence_contracts():
    plan = build_rnaseq_production_plan(_request(differential_expression_requested=True, fusion_detection_requested=True))
    assert plan["analysis_contract"]["differential_expression"] == "SEPARATE_EVIDENCE_REQUIRED"
    assert plan["analysis_contract"]["fusion_detection"] == "SEPARATE_EVIDENCE_REQUIRED"


def test_rnaseq_preview_dag_is_nonempty_but_has_production_boundary():
    pipe = build_dag("RNA-seq")
    steps = [stage.step for stage in pipe.stages]
    assert "rna_read_summary" in steps
    assert "rna_production_boundary" in steps
    assert "variant_calling" not in steps
