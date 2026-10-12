"""Build publication/deposition-ready reproducibility bundles from experiments."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.experiment import archive_manifest, doi_export_metadata, get_experiment
from app.services.reproducibility import enforce, get_ledger


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _requirements(versions: dict[str, str]) -> str:
    rows=[]
    for name, version in sorted((versions or {}).items()):
        if version and version != "unknown": rows.append(f"{name}=={version}")
    return "\n".join(rows)+("\n" if rows else "")


def _environment_yml(versions: dict[str,str]) -> str:
    pip=[f"      - {k}=={v}" for k,v in sorted((versions or {}).items()) if v and v!="unknown"]
    return "name: bionexus-reproducible\nchannels:\n  - conda-forge\ndependencies:\n  - python\n  - pip\n  - pip:\n"+"\n".join(pip)+"\n"


def _citation_cff(exp: dict) -> str:
    version=str(exp.get("version") or 1)
    return (
      "cff-version: 1.2.0\n"
      "message: \"If you use this BioNexus experiment, cite the archived experiment and software release.\"\n"
      f"title: \"BioNexus experiment {exp['experiment_id']}\"\n"
      "type: dataset\n"
      f"version: \"{version}\"\n"
      "authors:\n  - name: \"BioNexus user\"\n"
    )


def _dockerfile(exp: dict) -> str:
    digest=exp.get("container_hash")
    comment=f"# Recorded container/image identifier: {digest}\n" if digest else "# No immutable image digest was recorded for this run.\n"
    return comment+"FROM python:3.11-slim\nWORKDIR /workspace\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nCMD [\"python\", \"-m\", \"app\"]\n"


def _ro_crate(exp:dict, archive:dict)->dict:
    return {
      "@context":"https://w3id.org/ro/crate/1.1/context",
      "@graph":[
        {"@id":"ro-crate-metadata.json","@type":"CreativeWork","about":{"@id":"./"}},
        {"@id":"./","@type":"Dataset","name":f"BioNexus experiment {exp['experiment_id']}","version":str(exp.get("version") or 1),"identifier":exp["experiment_id"],"hasPart":[{"@id":"experiment.json"},{"@id":"experiment-manifest.json"},{"@id":"software-manifest.json"},{"@id":"execution-contract.json"},{"@id":"reproducibility-ledger.json"}]},
        {"@id":"experiment-manifest.json","@type":"File","sha256":archive["manifest_sha256"]},
      ]
    }


def _execution_contract(exp: dict) -> dict:
    return {
      "schema": "bionexus-execution-contract/v1",
      "experiment_id": exp.get("experiment_id"),
      "git_commit": exp.get("git_commit"),
      "container_digest": exp.get("container_hash"),
      "software_versions": exp.get("software_versions") or {},
      "database_versions": exp.get("database_versions") or {},
      "parameters": exp.get("parameters") or exp.get("settings") or {},
      "random_seed": exp.get("random_seed") or exp.get("seed"),
      "input_hashes": exp.get("input_hashes") or {},
      "output_hash": exp.get("output_hash"),
      "environment": exp.get("environment") or {},
      "doi": exp.get("doi"),
      "doi_status": "recorded" if exp.get("doi") else "not_minted_or_not_recorded",
      "reproduction_status": "contract_only",
      "boundary": "This contract records what is needed to reproduce the experiment. Presence of the contract alone does not prove that an independent reproduction has succeeded."
    }


def _readme(exp: dict, ledger_report: dict) -> str:
    state = "PASS" if ledger_report.get("valid") else "INCOMPLETE"
    return (
      f"# BioNexus reproducibility bundle\n\n"
      f"Experiment: `{exp.get('experiment_id')}`\n\n"
      f"Ledger status: **{state}**\n\n"
      "This bundle contains the experiment record, environment definitions, software/database versions, execution contract, checksums, RO-Crate metadata and DOI-deposition metadata.\n\n"
      "## Reproduction rule\n\n"
      "A reviewer should verify SHA256SUMS first, reconstruct the declared environment, obtain any external databases using the pinned versions/accessions, and execute the recorded analysis with the recorded parameters and seed. A missing external asset or immutable version must be reported rather than silently replaced.\n\n"
      "## Scientific boundary\n\n"
      "A complete bundle supports reproducibility auditing. It does not by itself establish biological correctness, external validation, or clinical validity.\n"
    )


def build_bundle(job_id:str)->dict[str,Any] | None:
    exp=get_experiment(job_id)
    if not exp:return None
    archive=archive_manifest(exp); versions=exp.get("software_versions") or {}; ledger=get_ledger(job_id); ledger_report=enforce(ledger)
    software_manifest={"git_commit":exp.get("git_commit"),"container_hash":exp.get("container_hash"),"software_versions":versions,"database_versions":exp.get("database_versions") or {},"environment":exp.get("environment") or {}}
    execution_contract=_execution_contract(exp)
    files={
      "README.md":_readme(exp, ledger_report),
      "Dockerfile":_dockerfile(exp),
      "requirements.txt":_requirements(versions),
      "environment.yml":_environment_yml(versions),
      "CITATION.cff":_citation_cff(exp),
      "experiment.json":json.dumps(exp,indent=2,sort_keys=True,default=str),
      "experiment-manifest.json":json.dumps(archive,indent=2,sort_keys=True,default=str),
      "execution-contract.json":json.dumps(execution_contract,indent=2,sort_keys=True,default=str),
      "software-manifest.json":json.dumps(software_manifest,indent=2,sort_keys=True,default=str),
      "ro-crate-metadata.json":json.dumps(_ro_crate(exp,archive),indent=2,sort_keys=True),
      "zenodo-metadata.json":json.dumps(doi_export_metadata(exp),indent=2,sort_keys=True,default=str),
      "reproducibility-ledger.json":json.dumps(ledger or {},indent=2,sort_keys=True,default=str),
    }
    checksums={name:_sha(content) for name,content in files.items()}; files["SHA256SUMS"]="\n".join(f"{digest}  {name}" for name,digest in sorted(checksums.items()))+"\n"
    return {"schema":"bionexus-reproducibility-bundle/v2","experiment_id":exp["experiment_id"],"ledger_validation":ledger_report,"execution_contract":execution_contract,"files":files,"checksums":{**checksums,"SHA256SUMS":_sha(files["SHA256SUMS"])},"warning":None if ledger_report.get("valid") else "Bundle generated, but the reproducibility ledger is incomplete or invalid; do not describe this run as fully reproducible until the ledger passes."}
