"""Objective comparative evaluation for BioNexus and peer platforms.

The evaluator consumes observed audit records; it never infers subjective ease
of use or UI quality. Scores therefore describe evidence completeness for a
specified run set, not general product superiority.
"""
from __future__ import annotations

from typing import Any

CRITERIA = {
    "reproducibility": ["immutable_run_id","input_checksum","output_checksum","code_version","software_versions","database_versions","container_or_environment","random_seed","parameter_snapshot"],
    "workflow_traceability": ["ordered_steps","node_dependencies","tool_versions","parameter_provenance","database_provenance","timestamps"],
    "provenance_completeness": ["input_lineage","computation_lineage","ai_lineage","figure_lineage","export_lineage"],
    "failure_transparency": ["failed_stage_visible","error_reason_visible","partial_results_labelled","fallbacks_labelled"],
    "benchmark_coverage": ["benchmark_registry","ground_truth_declared","acceptance_rule_declared","raw_results_retained","failed_cases_retained"],
    "export_quality": ["machine_readable_export","checksums","software_manifest","ro_crate","citation_metadata","publication_figure_metadata"],
    "scientific_reporting_completeness": ["methods","results","sample_size","statistical_method","confidence_interval_when_applicable","data_availability","code_availability","limitations"],
}


def _bool(record:dict,key:str)->bool:
    value=record.get(key)
    if isinstance(value,bool): return value
    if isinstance(value,(int,float)): return value>0
    return bool(value)


def evaluate_run(record:dict[str,Any])->dict:
    categories={}
    total_pass=total_items=0
    for category,fields in CRITERIA.items():
        checks=[{"field":field,"passed":_bool(record,field)} for field in fields]
        passed=sum(1 for c in checks if c["passed"]); total_pass+=passed; total_items+=len(checks)
        categories[category]={"passed":passed,"total":len(checks),"fraction":passed/len(checks),"checks":checks}
    return {"run_id":record.get("run_id"),"categories":categories,"overall_fraction":total_pass/total_items if total_items else 0.0,"passed_fields":total_pass,"total_fields":total_items}


def evaluate_platform(name:str,run_records:list[dict[str,Any]])->dict:
    evaluated=[evaluate_run(r) for r in run_records]
    n=len(evaluated); categories={}
    for category in CRITERIA:
        fractions=[r["categories"][category]["fraction"] for r in evaluated]
        categories[category]={"mean_fraction":sum(fractions)/n if n else None,"sample_size":n,"per_run":fractions}
    overall=[r["overall_fraction"] for r in evaluated]
    return {"platform":name,"sample_size":n,"criteria":categories,"overall_mean_fraction":sum(overall)/n if n else None,"runs":evaluated,"interpretation_boundary":"Scores measure supplied audit evidence for these runs only; they do not establish general platform superiority or usability."}


def compare_platforms(platform_runs:dict[str,list[dict[str,Any]]])->dict:
    platforms=[evaluate_platform(name,runs) for name,runs in sorted(platform_runs.items())]
    return {"schema":"bbs2-comparative-evaluation/v1","criteria":CRITERIA,"platforms":platforms,"ranking":None,"reason_no_ranking":"No composite superiority ranking is produced because criteria weighting would be subjective. Compare category-level measurements with sample sizes instead."}
