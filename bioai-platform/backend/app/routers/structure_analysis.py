import io
import math
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

# ── Structure Comparison (TM-Align via PDBeFold) ──────────

class StructureMatch(BaseModel):
    pdb_id: str
    chain: str
    description: str
    tm_score: float
    rmsd: float
    seq_identity: float
    aligned_length: int

@router.get("/compare/{pdb_id}")
async def compare_structures(pdb_id: str, chain: str = Query(default="A"), max_results: int = Query(default=10)):
    pdb_id = pdb_id.upper()

    fold_url = "https://www.ebi.ac.uk/msd-srv/ssm/rest/v1/compare"
    payload = {
        "queryId":    f"{pdb_id.lower()}:{chain}",
        "dbId":       "pdb",
        "mode":       "normal",
        "nResults":   max_results,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(fold_url, json=payload)
        if r.status_code != 200:
            raise HTTPException(502, f"PDBeFold returned {r.status_code}: {r.text[:200]}")
        data = r.json()

    results: list[StructureMatch] = []
    for hit in data.get("hits", []):
        results.append(StructureMatch(
            pdb_id         = hit.get("pdbId", "").upper(),
            chain          = hit.get("chainId", ""),
            description    = hit.get("description", ""),
            tm_score       = hit.get("tmScore", 0),
            rmsd           = hit.get("rmsd", 0),
            seq_identity   = hit.get("seqIdentity", 0),
            aligned_length = hit.get("nAlign", 0),
        ))
    results.sort(key=lambda x: x.tm_score, reverse=True)
    return {"query": f"{pdb_id}:{chain}", "matches": results}
