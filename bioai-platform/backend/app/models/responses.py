from pydantic import BaseModel, Field
from typing import Any, Literal, Optional


class PipelineRunResponse(BaseModel):
    job_id: str
    status: str


class PipelineDefinitionResponse(BaseModel):
    pipelines: list[dict[str, Any]]


class JobCountResponse(BaseModel):
    count: int
    limit: int
    remaining: int


class JobDeleteResponse(BaseModel):
    status: str


class InterpretResponse(BaseModel):
    prompt: str
    context_size: int


class WaitlistResponse(BaseModel):
    status: str
    email: str


class ProfileUpdateResponse(BaseModel):
    status: str
    data: Optional[dict[str, Any]] = None


class ErrorResponse(BaseModel):
    detail: str


class NgsProductionPlanRequest(BaseModel):
    assay: Literal["WGS", "WES"]
    sample_model: Literal["singleton", "cohort", "duo", "trio", "family"] = "singleton"
    input_type: Literal["FASTQ", "BAM", "CRAM"] = "FASTQ"
    start_step: Literal["mapping", "markduplicates", "variant_calling"] = "mapping"
    samplesheet_path: str = Field(min_length=1)
    outdir: str = Field(min_length=1)
    genome: Literal["GRCh38", "GRCh37"] = "GRCh38"
    execution_profile: Literal["docker", "singularity", "apptainer", "slurm", "awsbatch"] = "docker"
    caller: Literal["haplotypecaller", "deepvariant"] = "haplotypecaller"
    target_bed: Optional[str] = None
    custom_config: Optional[str] = None
    annotate_with_vep: bool = True
    clinical_intent: bool = False


class NgsProductionPlanResponse(BaseModel):
    schema_version: str
    workflow: dict[str, str]
    state: Literal["PLANNED", "BLOCKED"]
    ready_to_launch: bool
    blockers: list[str]
    warnings: list[str]
    command_argv: list[str]
    command_display: str
    required_artifacts: list[dict[str, Any]]
    provenance_requirements: list[str]
    clinical_boundary: dict[str, Any]


class NgsClinicalEvidenceRequest(BaseModel):
    evidence_bundle_sha256: Optional[str] = None
    evidence_signature: Optional[str] = None
    assay_validation_id: Optional[str] = None
    workflow_status: Literal["PLANNED", "COMPLETED", "FAILED"] = "PLANNED"
    sarek_revision: Optional[str] = None
    reference_build: Optional[Literal["GRCh38", "GRCh37"]] = None
    reference_manifest_sha256: Optional[str] = None
    samplesheet_sha256: Optional[str] = None
    container_digests_complete: bool = False
    complete_input_processed: bool = False
    required_artifacts_present: bool = False
    qc_pass: bool = False
    sample_identity_pass: bool = False
    contamination_pass: bool = False
    sex_ploidy_reviewed: bool = False
    truthset_name: Optional[str] = None
    benchmark_protocol_id: Optional[str] = None
    benchmark_acceptance_pass: bool = False
    confident_regions_sha256: Optional[str] = None
    same_sample_reference_regions: bool = False
    snv_precision: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    snv_recall: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    indel_precision: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    indel_recall: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    human_reviewed: bool = False
    reviewer_id: Optional[str] = None
    release_signature_id: Optional[str] = None
    unresolved_deviations: list[str] = Field(default_factory=list)


class NgsClinicalEvidenceResponse(BaseModel):
    schema_version: str
    status: Literal["SOFTWARE_GATE_PASSED", "NOT_CLINICALLY_RELEASABLE"]
    clinically_validated: Literal[False]
    gates: list[dict[str, Any]]
    missing_or_failed: list[str]
    benchmark_summary: dict[str, Any]
    disclaimer: str
