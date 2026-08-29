"""CASTp pocket/cavity analysis endpoints.

Pipeline (single identifier input): search PDB -> resolve to UniProt -> use a
linked experimental structure or model via ESMFold -> run CASTp pocket analysis
-> return the full resolution trace so the UI can show exactly which database
and step produced the structure, like the CASTp site does.
"""

import logging
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any

from app.services.identifier_resolution import is_uniprot_accession, resolve_to_uniprot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/castp", tags=["CASTp"])

_PDB_ID_RE = re.compile(r"^[A-Za-z0-9]{4}$")
# A raw amino-acid sequence is a long run of protein letters (with optional
# spaces/newlines); gene names / accessions are short identifiers.
_AA_ALPHABET = set("ACDEFGHIKLMNPQRSTVWY")


def _looks_like_sequence(ident: str) -> bool:
    ident = (ident or "").replace("\n", "").replace(" ", "").replace("-", "").replace(".", "")
    if len(ident) < 15:
        return False
    if not all(c in _AA_ALPHABET for c in ident.upper()):
        return False
    return bool(set(ident.upper()) & {"A", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M", "N", "P", "Q", "R", "S", "T", "V", "W", "Y"})


class CastpRequest(BaseModel):
    pdb_id: str = Field(default="", description="Unified identifier: PDB ID, UniProt accession, gene name, or raw sequence")
    sequence: str = Field(default="", description="Backward-compat: raw amino acid sequence")
    pdb_text: str = Field(default="", description="Raw PDB text content")
    probe_radius: float = Field(default=1.4, ge=0.0, le=5.0, description="Probe radius in Angstroms")


class ChainGap(BaseModel):
    start: int
    end: int
    count: int


class ChainInfo(BaseModel):
    id: str
    residue_count: int
    sequence: str
    gaps: list[ChainGap] = []


class PocketResidue(BaseModel):
    chain: str
    residue_number: int
    residue_name: str
    one: str
    label: str
    coordinate_present: bool = False


class PocketGap(BaseModel):
    chain: str
    gaps: list[ChainGap]


class ChainSpan(BaseModel):
    chain: str
    min: int
    max: int
    count: int


class ActiveSiteResidue(BaseModel):
    chain: str
    residue_number: int
    residue_name: str
    role: str = ""
    source: str = "M-CSA"


class PocketInfo(BaseModel):
    id: int
    area_sa: float
    volume_sa: float
    num_residues: int
    residues: list[str]
    centroid: list[float]
    radius: float
    residue_details: list[PocketResidue] = []
    gap_ranges: list[PocketGap] = []
    chain_spans: list[ChainSpan] = []
    active_site_hits: list[ActiveSiteResidue] = []


class PipelineStep(BaseModel):
    step: str
    status: str
    detail: str


class UniProtSummary(BaseModel):
    accession: str = ""
    name: str = ""
    organism: str = ""
    gene_names: list[str] = []
    sequence_length: int = 0


class CastpResponse(BaseModel):
    pdb_id: str
    probe_radius: float
    total_residues: int
    pockets: list[PocketInfo]
    sequence_source: str = ""
    structure_source: str = ""
    structure_pdb: str = Field(default="", description="Resolved structure PDB text (modeled/uploaded only; RCSB PDBs load by id)")
    pipeline: list[PipelineStep] = []
    uniprot: UniProtSummary | None = None
    chains: list[ChainInfo] = []
    active_sites: list[ActiveSiteResidue] = []


async def _fetch_pdb_rcsb(pdb_id: str) -> str:
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb")
        if resp.status_code != 200:
            raise RuntimeError(f"PDB {pdb_id.upper()} not found on RCSB")
        return resp.text


async def _uniprot_summary(accession: str) -> UniProtSummary:
    from app.tools.uniprot import UniprotTool
    try:
        data = await UniprotTool().run({"accession": accession})
        if "error" in data:
            return UniProtSummary(accession=accession, name="", organism="", gene_names=[], sequence_length=0)
        return UniProtSummary(
            accession=data.get("accession", accession),
            name=data.get("full_name", ""),
            organism=data.get("organism", ""),
            gene_names=data.get("gene_names", []) or [],
            sequence_length=data.get("sequence_length", 0),
        )
    except Exception as exc:
        logger.warning("UniProt summary failed for %s: %s", accession, exc)
        return UniProtSummary(accession=accession, name="", organism="", gene_names=[], sequence_length=0)


async def _resolve_pipeline(identifier: str) -> dict[str, Any]:
    """Resolve an identifier to structure text via PDB -> UniProt -> model.

    Returns dict with pdb_text, pdb_id, source, provenance, uniprot.
    """
    ident = (identifier or "").strip()
    provenance: list[dict] = []
    uniprot: UniProtSummary | None = None
    pdb_text: str | None = None
    pdb_id = ident.upper()
    source = ""

    # Step 1 — look for an existing PDB entry first.
    if _PDB_ID_RE.match(ident):
        try:
            pdb_text = await _fetch_pdb_rcsb(ident.upper())
            pdb_id = ident.upper()
            source = "pdb"
            provenance.append({"step": "pdb", "status": "ok", "detail": f"Found {ident.upper()} in the RCSB PDB"})
        except Exception as exc:
            provenance.append({"step": "pdb", "status": "skip", "detail": f"No PDB entry {ident.upper()} on RCSB ({type(exc).__name__})"})
    elif is_uniprot_accession(ident):
        provenance.append({"step": "pdb", "status": "skip", "detail": f"{ident} is a UniProt accession (not a PDB ID)"})
    else:
        provenance.append({"step": "pdb", "status": "skip", "detail": f"{ident} is not a 4-character PDB ID"})

    # Raw sequence input — model it directly, no UniProt lookup needed.
    if pdb_text is None and _looks_like_sequence(ident):
        seq = ident.replace("\n", "").replace(" ", "").replace("-", "").replace(".", "")
        provenance.append({"step": "sequence", "status": "ok", "detail": f"Detected a {len(seq)}-residue amino-acid sequence"})
        provenance.append({"step": "uniprot", "status": "skip", "detail": "Raw sequence provided; modeling directly"})
        modeled = await _esmfold_or_raise(seq, provenance)
        pdb_text = modeled
        pdb_id = "predicted"
        source = "model_esmfold"
        return {"pdb_text": pdb_text, "pdb_id": pdb_id, "source": source, "provenance": provenance, "uniprot": uniprot}

    # Step 2 — resolve to UniProt.
    if pdb_text is None and ident and not _looks_like_sequence(ident):
        resolved = await resolve_to_uniprot(accession=ident)
        if resolved.get("status") == "resolved" and resolved.get("accession"):
            acc = resolved["accession"]
            method = resolved.get("method", "")
            provenance.append({"step": "uniprot", "status": "ok", "detail": f"Mapped {ident} -> UniProt {acc} ({method})"})
            uniprot = await _uniprot_summary(acc)
            # 2a — UniProt-linked experimental structure.
            linked = await _linked_pdb(acc)
            if linked:
                try:
                    pdb_text = await _fetch_pdb_rcsb(linked)
                    pdb_id = linked
                    source = "uniprot_pdb"
                    provenance.append({"step": "structure", "status": "ok", "detail": f"UniProt {acc} is linked to experimental structure {linked}; using it"})
                except Exception as exc:
                    provenance.append({"step": "structure", "status": "skip", "detail": f"Linked PDB {linked} unavailable ({type(exc).__name__})"})
            # 2b — model the UniProt sequence.
            if pdb_text is None:
                if uniprot.sequence_length > 0:
                    seq = await _uniprot_sequence(acc)
                    if seq:
                        provenance.append({"step": "structure", "status": "ok", "detail": f"No experimental structure for {acc}; modeling {len(seq)} aa via ESMFold"})
                        pdb_text = await _esmfold_or_raise(seq, provenance)
                        pdb_id = "predicted"
                        source = "model_esmfold"
                    else:
                        provenance.append({"step": "structure", "status": "error", "detail": f"UniProt {acc} returned no sequence"})
                else:
                    provenance.append({"step": "structure", "status": "error", "detail": f"No sequence available for {acc}"})
        else:
            provenance.append({"step": "uniprot", "status": "error", "detail": f"Could not map {ident} to a UniProt entry"})

    return {"pdb_text": pdb_text, "pdb_id": pdb_id, "source": source, "provenance": provenance, "uniprot": uniprot}


async def _linked_pdb(accession: str) -> str | None:
    from app.tools.uniprot import UniprotTool
    try:
        data = await UniprotTool().run({"accession": accession})
        pdbs = data.get("pdb_ids") or []
        return pdbs[0] if pdbs else None
    except Exception:
        return None


async def _uniprot_sequence(accession: str) -> str | None:
    from app.tools.uniprot import UniprotTool
    try:
        data = await UniprotTool().run({"accession": accession})
        seq = data.get("sequence", "") or ""
    except Exception as exc:
        logger.warning("UniProt sequence fetch failed for %s: %s", accession, exc)
        return None
    return seq if seq else None


async def _esmfold_or_raise(seq: str, provenance: list[dict]) -> str:
    from app.tools.structure_prep import esmfold_predict
    if len(seq) < 10:
        raise HTTPException(status_code=400, detail="Sequence too short (min 10 residues)")
    if len(seq) > 400:
        raise HTTPException(status_code=400, detail="Sequence too long (max 400 residues for ESMFold)")
    modeled = await esmfold_predict(seq)
    if not modeled:
        provenance.append({"step": "structure", "status": "error", "detail": "ESMFold could not predict a valid structure"})
        raise HTTPException(status_code=400, detail="ESMFold could not predict a valid structure for this sequence")
    return modeled


async def _csa_active_sites(accession: str, pdb_id: str, uniprot_seq: str = "") -> dict:
    """Fetch M-CSA catalytic residues for a UniProt accession.

    Returns {"direct": [...], "uniprot_positions": [...], "uniprot_seq": str}
    where ``direct`` are residues annotated on the given PDB (chain + residue
    number) and ``uniprot_positions`` are residues referenced by UniProt
    sequence position [{uniprot_resid, one, code, role}] for homology mapping.
    """
    if not accession:
        return {"direct": [], "uniprot_positions": [], "uniprot_seq": uniprot_seq}
    import httpx
    url = (
        "https://www.ebi.ac.uk/thornton-srv/m-csa/api/residues/"
        f"?format=json&entries.proteins.sequences.uniprot_ids={accession}"
    )
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {"direct": [], "uniprot_positions": [], "uniprot_seq": uniprot_seq}
            entries = resp.json()
    except Exception as exc:
        logger.warning("M-CSA lookup failed for %s: %s", accession, exc)
        return {"direct": [], "uniprot_positions": [], "uniprot_seq": uniprot_seq}

    pdb_l = pdb_id.lower() if pdb_id else ""
    direct: list[dict] = []
    uniprot_positions: list[dict] = []
    seen_upos: set[int] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        role = entry.get("roles_summary") or entry.get("main_annotation") or ""
        for rc in entry.get("residue_chains", []) or []:
            if pdb_l and str(rc.get("pdb_id", "")).lower() == pdb_l:
                direct.append({
                    "chain": str(rc.get("assembly_chain_name") or rc.get("chain_name") or ""),
                    "residue_number": int(rc.get("auth_resid") or rc.get("resid") or 0),
                    "residue_name": rc.get("code", ""),
                    "one": _CODON_TO_AA.get(rc.get("code", ""), rc.get("code", "")),
                    "role": role,
                    "source": "M-CSA",
                })
        for rs in entry.get("residue_sequences", []) or []:
            pos = rs.get("resid")
            code = rs.get("code", "")
            if pos is None or pos in seen_upos:
                continue
            seen_upos.add(pos)
            uniprot_positions.append({
                "uniprot_resid": int(pos),
                "code": code,
                "one": _CODON_TO_AA.get(code, code),
                "role": role,
            })
    return {
        "direct": direct,
        "uniprot_positions": uniprot_positions,
        "uniprot_seq": uniprot_seq,
    }


def _nw_align_to_uniprot(chain_seq: str, uniprot_seq: str) -> list[int]:
    """Needleman-Wunsch global alignment; returns a per-uniprot-index map to
    chain index (or -1 for a gap in the chain), so UniProt residue positions
    can be transferred onto the loaded structure's residue numbers."""
    a = chain_seq
    b = uniprot_seq
    m, n = len(a), len(b)
    gap, match, mismatch = -1, 2, -1
    # DP over (chain_len_used, uniprot_len_used)
    score = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        score[i][0] = score[i - 1][0] + gap
    for j in range(1, n + 1):
        score[0][j] = score[0][j - 1] + gap
    for i in range(1, m + 1):
        ai = score[i]
        prev = score[i - 1]
        for j in range(1, n + 1):
            diag = prev[j - 1] + (match if a[i - 1] == b[j - 1] else mismatch)
            ai[j] = max(diag, prev[j] + gap, ai[j - 1] + gap)
    # Traceback; maps uniprot column -> chain char index (or None)
    uniprot_to_chain: list[int] = []
    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0 and score[i][j] == score[i - 1][j - 1] + (match if a[i - 1] == b[j - 1] else mismatch):
            uniprot_to_chain.append(i - 1)
            i -= 1
            j -= 1
        elif i > 0 and score[i][j] == score[i - 1][j] + gap:
            # chain residue consumed, uniprot gap -> not a valid map
            uniprot_to_chain.append(-1)
            i -= 1
        else:
            uniprot_to_chain.append(-1)
            j -= 1
    uniprot_to_chain.reverse()
    return uniprot_to_chain


def _map_uniprot_positions(active: dict, chains: list[dict]) -> list[dict]:
    """Place CSA UniProt-referenced catalytic residues onto the structure
    chains by aligning each chain's observed sequence to the UniProt
    sequence and transferring residue positions."""
    uniprot_seq = (active.get("uniprot_seq") or "").upper()
    positions = active.get("uniprot_positions") or []
    if not uniprot_seq or not positions or not chains:
        return []

    mapped: list[dict] = []
    for chain in chains:
        residues = chain.get("residues", [])
        chain_seq = "".join(r["one"] for r in residues).upper()
        if not chain_seq:
            continue
        mapping = _nw_align_to_uniprot(chain_seq, uniprot_seq)
        for p in positions:
            pos = p.get("uniprot_resid")
            if not pos or pos - 1 >= len(mapping):
                continue
            chain_idx = mapping[pos - 1]
            if chain_idx is None or chain_idx < 0 or chain_idx >= len(residues):
                continue
            mapped.append({
                "chain": chain["id"],
                "residue_number": residues[chain_idx]["num"],
                "residue_name": p.get("code", ""),
                "one": p.get("one", ""),
                "role": p.get("role", ""),
                "source": "M-CSA (sequence mapped)",
            })
    return mapped


_CODON_TO_AA = {
    "Gly": "G", "Ala": "A", "Val": "V", "Leu": "L", "Ile": "I", "Pro": "P",
    "Phe": "F", "Trp": "W", "Met": "M", "Ser": "S", "Thr": "T", "Cys": "C",
    "Tyr": "Y", "Asn": "N", "Gln": "Q", "Asp": "D", "Glu": "E", "Lys": "K",
    "Arg": "R", "His": "H", "Sec": "U",
}


def _match_active_sites(pocket: dict, sites: list[dict]) -> list[dict]:
    """Determine which active-site residues fall within a pocket's lining
    residues (matched by chain + residue number)."""
    if not sites:
        return []
    span_by_chain = {}
    for r in pocket.get("residue_details", []):
        if r.get("chain"):
            chain_res = span_by_chain.setdefault(r["chain"], set())
            chain_res.add(r.get("residue_number"))
    hits = []
    for site in sites:
        chain = site.get("chain", "")
        nums = span_by_chain.get(chain)
        if nums is not None and site.get("residue_number") in nums:
            hits.append({**site})
    return hits


@router.post("/analyze", response_model=CastpResponse)
async def analyze_castp(body: CastpRequest):
    from app.tools.castp import analyze_pockets_pdb_text

    probe = body.probe_radius
    provenance: list[PipelineStep] = []
    uniprot: UniProtSummary | None = None
    structure_source = ""
    pdb_text: str | None = None
    pdb_id = "custom"

    if body.pdb_text.strip():
        pdb_text = body.pdb_text.strip()
        pdb_id = "custom"
        structure_source = "pdb_text"
        provenance.append({"step": "input", "status": "ok", "detail": "Analyzing uploaded PDB text directly"})
    elif body.sequence.strip():
        seq = body.sequence.strip().upper().replace("\n", "").replace(" ", "").replace("-", "")
        if len(seq) < 10:
            raise HTTPException(status_code=400, detail="Sequence too short (min 10 residues)")
        if len(seq) > 400:
            raise HTTPException(status_code=400, detail="Sequence too long (max 400 residues for ESMFold)")
        provenance.append({"step": "sequence", "status": "ok", "detail": f"Received {len(seq)}-residue amino-acid sequence"})
        modeled = await _esmfold_or_raise(seq, provenance)
        pdb_text = modeled
        pdb_id = "predicted"
        structure_source = "model_esmfold"
        provenance.append({"step": "structure", "status": "ok", "detail": "Modeled structure via ESMFold, then running CASTp"})
    elif body.pdb_id.strip():
        resolution = await _resolve_pipeline(body.pdb_id)
        pdb_text = resolution["pdb_text"]
        pdb_id = resolution["pdb_id"]
        structure_source = resolution["source"]
        provenance = [PipelineStep(**s) for s in resolution["provenance"]]
        uniprot = resolution["uniprot"]
        if not pdb_text:
            detail = " / ".join(p.detail for p in provenance if p.status == "error") or "Could not resolve the input to a structure"
            raise HTTPException(status_code=404, detail=detail)
    else:
        raise HTTPException(status_code=400, detail="Provide pdb_id, sequence, or pdb_text")

    result = await analyze_pockets_pdb_text(pdb_text, pdb_id, probe)

    # M-CSA active-site comparison (best-effort — never blocks the result).
    active_sites: list[dict] = []
    try:
        search_acc = uniprot.accession if uniprot else ""
        if not search_acc and structure_source in ("pdb", "uniprot_pdb"):
            resolved = await resolve_to_uniprot(accession=pdb_id)
            if resolved.get("status") == "resolved":
                search_acc = resolved.get("accession") or ""
        if search_acc:
            active = await _csa_active_sites(search_acc, pdb_id)
            active_sites = list(active["direct"])
            if not active_sites:
                # No direct CSA reference match: try mapping catalytic residues
                # by UniProt sequence position onto the loaded structure.
                up_seq = await _uniprot_sequence(search_acc)
                active["uniprot_seq"] = up_seq or ""
                from app.tools.castp import _parse_pdb_chains
                active_sites = _map_uniprot_positions(active, _parse_pdb_chains(pdb_text)["chains"])
            # de-duplicate by chain + residue number
            seen = set()
            deduped = []
            for site in active_sites:
                k = (site.get("chain"), site.get("residue_number"))
                if k in seen:
                    continue
                seen.add(k)
                deduped.append(site)
            active_sites = deduped
            provenance.append(PipelineStep(
                step="compare",
                status="ok" if active_sites else "skip",
                detail=(
                    f"Compared pocket lining residues with {len(active_sites)} M-CSA catalytic residues for {search_acc}"
                    if active_sites else "No curated M-CSA catalytic residues could be mapped to this structure"
                ),
            ))
    except Exception as exc:
        logger.warning("M-CSA comparison failed: %s", exc)

    # Only embed the PDB text for structures that can't be loaded from RCSB by
    # id (modeled / uploaded). For a real RCSB entry the viewer fetches it via
    # pdb_id, keeping the response lean.
    embed_pdb = structure_source in ("model_esmfold", "pdb_text")

    pockets = []
    for p in result.get("pockets", []):
        pocket_dict = dict(p)
        pocket_dict["active_site_hits"] = _match_active_sites(p, active_sites)
        pockets.append(PocketInfo(**pocket_dict))

    response = CastpResponse(
        pdb_id=result["pdb_id"],
        probe_radius=result["probe_radius"],
        total_residues=result["total_residues"],
        pockets=pockets,
        sequence_source=structure_source,
        structure_source=structure_source,
        structure_pdb=pdb_text if embed_pdb else "",
        pipeline=provenance,
        uniprot=uniprot,
        chains=[ChainInfo(**c) for c in result.get("chains", [])],
        active_sites=[ActiveSiteResidue(**a) for a in active_sites],
    )

    # AI interpretation (best-effort, never blocks)
    try:
        from app.ai.tool_interpreter import interpret_tool_result
        ai_interp = await interpret_tool_result("castp", result)
        if ai_interp:
            response_dict = response.model_dump()
            response_dict["ai_interpretation"] = ai_interp
            return response_dict
    except Exception:
        pass

    return response
