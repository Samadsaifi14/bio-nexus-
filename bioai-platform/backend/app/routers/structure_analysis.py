import asyncio
import io
import math
import secrets
import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from Bio.PDB import PDBParser, PPBuilder

router = APIRouter(prefix="/api/structure_analysis", tags=["structure_analysis"])

# ── Ramachandran ──────────────────────────────────────────

class RamachandranPoint(BaseModel):
    residue: str
    chain: str
    resnum: int
    phi: float
    psi: float
    region: str

def classify_rama(phi: float, psi: float) -> str:
    def in_region(p, q, cp, cq, rp, rq):
        return abs(p - cp) < rp and abs(q - cq) < rq
    if in_region(phi, psi, -57, -47, 30, 30):
        return "core_alpha"
    if in_region(phi, psi, -119, 113, 30, 30):
        return "core_beta"
    if phi < 0:
        return "allowed"
    return "outlier"

@router.get("/ramachandran/{pdb_id}", response_model=list[RamachandranPoint])
async def ramachandran(pdb_id: str, chain: str = Query(default="A")):
    pdb_id = pdb_id.upper()

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"https://files.rcsb.org/download/{pdb_id}.pdb")
        if r.status_code != 200:
            r = await client.get(
                f"https://alphafold.ebi.ac.uk/files/AF-{pdb_id}-F1-model_v4.pdb"
            )
        if r.status_code != 200:
            raise HTTPException(404, f"PDB not found: {pdb_id}")
        pdb_data = r.text

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("protein", io.StringIO(pdb_data))
    builder = PPBuilder()

    points: list[RamachandranPoint] = []
    for model in structure:
        for ch in model:
            if chain and ch.id != chain:
                continue
            for pp in builder.build_peptides(ch):
                phi_psi = pp.get_phi_psi_list()
                for residue, angles in zip(pp, phi_psi):
                    phi, psi = angles
                    if phi is None or psi is None:
                        continue
                    phi_deg = math.degrees(phi)
                    psi_deg = math.degrees(psi)
                    points.append(RamachandranPoint(
                        residue=residue.get_resname(),
                        chain=ch.id,
                        resnum=residue.get_id()[1],
                        phi=round(phi_deg, 2),
                        psi=round(psi_deg, 2),
                        region=classify_rama(phi_deg, psi_deg),
                    ))
    if not points:
        raise HTTPException(404, "No φ/ψ angles found — check chain ID")
    return points

# ── Secondary Structure ───────────────────────────────────

CF_PROPENSITY: dict[str, tuple[float, float]] = {
    "ALA": (1.42, 0.83), "ARG": (0.98, 0.93), "ASN": (0.67, 0.89),
    "ASP": (1.01, 0.54), "CYS": (0.70, 1.19), "GLN": (1.11, 1.10),
    "GLU": (1.51, 0.37), "GLY": (0.57, 0.75), "HIS": (1.00, 0.87),
    "ILE": (1.08, 1.60), "LEU": (1.21, 1.30), "LYS": (1.16, 0.74),
    "MET": (1.45, 1.05), "PHE": (1.13, 1.38), "PRO": (0.57, 0.55),
    "SER": (0.77, 0.75), "THR": (0.83, 1.19), "TRP": (1.08, 1.37),
    "TYR": (0.69, 1.47), "VAL": (1.06, 1.70),
}

AA1_TO_AA3 = {
    "A": "ALA", "R": "ARG", "N": "ASN", "D": "ASP", "C": "CYS",
    "Q": "GLN", "E": "GLU", "G": "GLY", "H": "HIS", "I": "ILE",
    "L": "LEU", "K": "LYS", "M": "MET", "F": "PHE", "P": "PRO",
    "S": "SER", "T": "THR", "W": "TRP", "Y": "TYR", "V": "VAL",
}

class SSResidue(BaseModel):
    position: int
    residue: str
    ss: str
    source: str

@router.get("/secondary_structure/{identifier}")
async def secondary_structure(identifier: str):
    identifier = identifier.upper()

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"https://rest.uniprot.org/uniprotkb/{identifier}.fasta"
        )
        if r.status_code != 200:
            raise HTTPException(404, f"Cannot find sequence for {identifier}")
        fasta = r.text
        seq = "".join(fasta.split("\n")[1:])

    WINDOW = 6
    ss_list: list[SSResidue] = []
    for i, aa in enumerate(seq):
        aa3 = AA1_TO_AA3.get(aa, "GLY")
        window_aas = seq[max(0, i - WINDOW):min(len(seq), i + WINDOW + 1)]
        h_avg = sum(CF_PROPENSITY.get(AA1_TO_AA3.get(a, "GLY"), (1.0, 1.0))[0] for a in window_aas) / len(window_aas)
        e_avg = sum(CF_PROPENSITY.get(AA1_TO_AA3.get(a, "GLY"), (1.0, 1.0))[1] for a in window_aas) / len(window_aas)
        if h_avg > 1.03 and h_avg >= e_avg:
            ss = "H"
        elif e_avg > 1.05 and e_avg > h_avg:
            ss = "E"
        else:
            ss = "C"
        ss_list.append(SSResidue(position=i + 1, residue=aa, ss=ss, source="predicted"))

    return {"identifier": identifier, "method": "Chou-Fasman (predicted)", "residues": ss_list}

# ── Structure Comparison (Foldseek) ────────────────────────

FOLDSEEK_BASE = "https://search.foldseek.com/api"

class StructureMatch(BaseModel):
    pdb_id: str
    chain: str
    description: str
    tm_score: float
    rmsd: float
    seq_identity: float
    aligned_length: int

def _extract_chain(pdb_text: str, chain_id: str) -> str:
    """Extract a single chain from a PDB file as a valid minimal PDB."""
    lines: list[str] = []
    for line in pdb_text.splitlines():
        if len(line) < 22:
            continue
        if line.startswith(("ATOM", "HETATM", "TER")):
            if line[21] == chain_id:
                lines.append(line)
        elif line.startswith(("END", "ENDMDL")):
            break
        elif line.startswith(("HEADER", "TITLE", "COMPND", "SOURCE",
                               "KEYWDS", "EXPDTA", "REMARK", "DBREF",
                               "SEQRES", "MODEL")):
            lines.append(line)
    if lines and not lines[-1].startswith("END"):
        lines.append("END")
    return "\n".join(lines)

@router.get("/compare/{pdb_id}")
async def compare_structures(pdb_id: str, chain: str = Query(default="A"),
                              max_results: int = Query(default=10, le=50)):
    pdb_id = pdb_id.upper()
    try:
        return await _foldseek_search(pdb_id, chain, max_results)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Foldseek error: {type(e).__name__}: {e}")

async def _foldseek_search(pdb_id: str, chain: str, max_results: int) -> dict:
    # 1. Fetch PDB file from RCSB
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"https://files.rcsb.org/download/{pdb_id}.pdb")
        if r.status_code != 200:
            raise HTTPException(404, f"PDB file not found: {pdb_id}")
        pdb_bytes = r.content

    # 2. Submit to Foldseek (sync client, blocking call in thread pool)
    import functools, json as _json
    def _submit():
        client = httpx.Client(timeout=30)
        try:
            resp = client.post(
                f"{FOLDSEEK_BASE}/ticket",
                files={"q": (f"{pdb_id}.pdb", pdb_bytes, "application/octet-stream")},
                data={"mode": "tmalign", "database[]": "pdb100"},
            )
            return resp.status_code, resp.text, str(dict(resp.headers))
        finally:
            client.close()
    loop = asyncio.get_event_loop()
    status, resp_text, resp_headers = await loop.run_in_executor(None, _submit)
    if status != 200:
        raise HTTPException(502, f"Foldseek submission failed (HTTP {status}): {resp_text[:500]}")
    try:
        resp_json = _json.loads(resp_text)
    except Exception as e:
        raise HTTPException(502, f"Foldseek bad JSON (HTTP {status}): {resp_text[:500]}")
    ticket = resp_json.get("id") if isinstance(resp_json, dict) else None
    if not ticket:
        raise HTTPException(502, f"Foldseek returned type={type(resp_json).__name__}, no id: {resp_text[:500]} | headers: {resp_headers[:300]}")

    # 3. Poll for results (up to ~120s) then fetch
    async with httpx.AsyncClient(timeout=120) as client:
        for _ in range(60):
            await asyncio.sleep(2)
            try:
                status = await client.get(f"{FOLDSEEK_BASE}/ticket/{ticket}")
                if status.status_code == 200:
                    s = status.json().get("status")
                    if s == "COMPLETE":
                        break
                    if s == "ERROR":
                        raise HTTPException(502, "Foldseek job failed")
            except HTTPException:
                raise
            except Exception:
                continue

        # 4. Fetch results - try multiple times since there's a race
        for attempt in range(3):
            result_resp = await client.get(f"{FOLDSEEK_BASE}/result/{ticket}/0")
            if result_resp.status_code == 200:
                data = result_resp.json()
                break
            if attempt < 2:
                await asyncio.sleep(2)
        else:
            raise HTTPException(504, "Foldseek job did not complete in time")

    # 5. Parse alignments
    entries = data if isinstance(data, list) else data.get("results", [])
    seen: set[str] = set()
    results: list[StructureMatch] = []
    for db_entry in entries:
        for aln in db_entry.get("alignments", []):
            target = aln.get("target", "")
            raw = target.replace("pdb_", "").replace("PDB_", "")
            match_pdb   = raw[:4].upper()
            match_chain = raw[4:] if len(raw) > 4 else ""

            if not match_pdb or (match_pdb == pdb_id and (not match_chain or match_chain == chain)):
                continue
            if match_pdb in seen:
                continue
            seen.add(match_pdb)

            tm = aln.get("score", 0) / 100.0
            results.append(StructureMatch(
                pdb_id=match_pdb,
                chain=match_chain,
                description=target,
                tm_score=round(tm, 4),
                rmsd=0,
                seq_identity=aln.get("seqId", 0),
                aligned_length=aln.get("alnLength", 0),
            ))
            if len(results) >= max_results:
                break
        if len(results) >= max_results:
            break

    if not results:
        raise HTTPException(404, "No structurally similar proteins found")
    results.sort(key=lambda x: x.tm_score, reverse=True)
    return {"query": f"{pdb_id}:{chain}", "matches": results}
