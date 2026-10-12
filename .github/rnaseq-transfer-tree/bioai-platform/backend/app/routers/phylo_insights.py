"""Post-processing utilities for phylogenetic trees.

Uses Bio.Phylo for deterministic Newick parsing/rooting and consensus. These
operations do not rerun phylogenetic inference; provenance must therefore keep
the source tree method/model/bootstrap separately.
"""
from __future__ import annotations

import io
from typing import Any, Literal

from Bio import Phylo
from Bio.Phylo.Consensus import majority_consensus
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/phylo/insights", tags=["phylo-insights"])


class RootRequest(BaseModel):
    newick: str = Field(..., min_length=3)
    method: Literal["midpoint", "outgroup"] = "midpoint"
    outgroup: str | None = None


class ConsensusRequest(BaseModel):
    trees: list[str] = Field(..., min_length=2)
    cutoff: float = Field(0.5, ge=0.5, le=1.0)


class OverlayRequest(BaseModel):
    newick: str = Field(..., min_length=3)
    metadata: dict[str, dict[str, Any]] = Field(default_factory=dict)


def _parse(newick: str):
    try:
        return Phylo.read(io.StringIO(newick.strip()), "newick")
    except Exception as exc:
        raise ValueError(f"invalid Newick: {exc}") from exc


def _newick(tree) -> str:
    handle = io.StringIO()
    Phylo.write(tree, handle, "newick")
    return handle.getvalue().strip()


def root_tree(newick: str, method: str = "midpoint", outgroup: str | None = None) -> dict:
    tree = _parse(newick)
    original_rooted = bool(tree.rooted)
    if method == "midpoint":
        try:
            tree.root_at_midpoint()
        except Exception as exc:
            raise ValueError(f"midpoint rooting failed: {exc}") from exc
        used = "midpoint"
    elif method == "outgroup":
        if not outgroup:
            raise ValueError("outgroup name is required for outgroup rooting")
        terminals = {t.name: t for t in tree.get_terminals() if t.name}
        if outgroup not in terminals:
            raise ValueError(f"outgroup '{outgroup}' is not a terminal in this tree")
        tree.root_with_outgroup(terminals[outgroup])
        used = f"outgroup:{outgroup}"
    else:
        raise ValueError(f"unsupported rooting method: {method}")
    tree.rooted = True
    return {
        "newick": _newick(tree),
        "rooting": used,
        "source_tree_was_rooted": original_rooted,
        "terminal_count": len(tree.get_terminals()),
        "scientific_boundary": "Rooting changes representation/interpretation of the supplied topology; it does not add phylogenetic evidence or rerun inference.",
    }


def consensus_tree(trees: list[str], cutoff: float = 0.5) -> dict:
    parsed = [_parse(t) for t in trees]
    terminal_sets = [{x.name for x in t.get_terminals()} for t in parsed]
    if not terminal_sets or any(s != terminal_sets[0] for s in terminal_sets[1:]):
        raise ValueError("all consensus input trees must contain the same terminal taxa")
    consensus = majority_consensus(parsed, cutoff=cutoff)
    supports = []
    for clade in consensus.find_clades(order="preorder"):
        if clade.is_terminal():
            continue
        conf = getattr(clade, "confidence", None)
        supports.append({
            "taxa": sorted(t.name for t in clade.get_terminals() if t.name),
            "support_pct": round(float(conf), 4) if conf is not None else None,
        })
    return {
        "newick": _newick(consensus),
        "tree_count": len(parsed),
        "cutoff": cutoff,
        "terminal_count": len(terminal_sets[0]),
        "clade_support": supports,
        "method": "Bio.Phylo majority-rule consensus",
        "scientific_boundary": "Consensus support summarizes supplied replicate trees; it is not a substitute for generating valid bootstrap/posterior replicate trees.",
    }


def metadata_overlay(newick: str, metadata: dict[str, dict[str, Any]]) -> dict:
    tree = _parse(newick)
    terminals = []
    missing = []
    for terminal in tree.get_terminals():
        name = terminal.name or ""
        meta = metadata.get(name)
        if meta is None:
            missing.append(name)
            meta = {}
        terminals.append({
            "name": name,
            "branch_length": terminal.branch_length,
            "metadata": meta,
        })
    unknown_metadata = sorted(set(metadata) - {t["name"] for t in terminals})
    return {
        "newick": newick,
        "terminals": terminals,
        "metadata_coverage": {
            "terminal_count": len(terminals),
            "annotated": sum(1 for t in terminals if t["metadata"]),
            "missing": missing,
            "metadata_without_terminal": unknown_metadata,
        },
    }


@router.post("/root")
def root_endpoint(body: RootRequest):
    try:
        return root_tree(body.newick, body.method, body.outgroup)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/consensus")
def consensus_endpoint(body: ConsensusRequest):
    try:
        return consensus_tree(body.trees, body.cutoff)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/metadata-overlay")
def overlay_endpoint(body: OverlayRequest):
    try:
        return metadata_overlay(body.newick, body.metadata)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
