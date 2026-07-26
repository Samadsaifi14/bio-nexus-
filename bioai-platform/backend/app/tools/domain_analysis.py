"""
Comprehensive Domain & Motif Analysis tool.

Aggregates data from InterPro (domain architecture) and UniProtKB (features,
functional sites, PTMs, topology, motifs, variants, GO terms, pathways).

Provides the shared analysis functions used by both the standalone router
and the pipeline_v2 orchestrator.
"""
import re
import httpx
from typing import Any


INTERPRO_API = "https://www.ebi.ac.uk/interpro/api/entry/all/protein/UniProt/{accession}/?format=json&page_size=50"
UNIPROT_API = "https://rest.uniprot.org/uniprotkb/{accession}.json"


def _sanitize(s: str) -> str:
    return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s).strip().upper()


async def fetch_uniprot_raw(accession: str) -> dict:
    """Fetch raw UniProt JSON for an accession."""
    accession = _sanitize(accession)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(UNIPROT_API.format(accession=accession))
        if resp.status_code in (400, 404):
            return {}
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# 1. InterPro Domain Architecture (existing, refactored)
# ---------------------------------------------------------------------------

async def fetch_interpro_domains(accession: str) -> dict:
    """Fetch domain annotations from InterPro (Pfam, SMART, PROSITE, CDD, PANTHER, PRINTS)."""
    accession = _sanitize(accession)
    url = INTERPRO_API.format(accession=accession)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        if r.status_code == 404:
            return {"uniprot_accession": accession, "sequence_length": 0, "domains": []}
        r.raise_for_status()
        data = r.json()

    domains: list[dict] = []
    seq_len = 0

    for result in data.get("results", []):
        entry = result.get("metadata", {})
        db = entry.get("source_database", "").upper()
        acc = entry.get("accession", "")
        name_raw = entry.get("name")
        if isinstance(name_raw, str):
            name_str = name_raw
        elif isinstance(name_raw, dict):
            name_str = name_raw.get("name", acc)
        else:
            name_str = acc

        for protein in result.get("proteins", []):
            if protein.get("accession", "").upper() != accession.upper():
                continue
            seq_len = protein.get("protein_length", seq_len)
            for loc in protein.get("entry_protein_locations", []):
                for fragment in loc.get("fragments", []):
                    domains.append({
                        "accession": acc,
                        "name": name_str,
                        "source_db": db,
                        "start": fragment.get("start", 0),
                        "end": fragment.get("end", 0),
                        "score": loc.get("score"),
                    })

    domains.sort(key=lambda d: d["start"])
    return {"uniprot_accession": accession, "sequence_length": seq_len, "domains": domains}


# ---------------------------------------------------------------------------
# 2. UniProt Feature Table
# ---------------------------------------------------------------------------

_FEATURE_CATEGORIES = {
    "active_sites":        {"Active site", "Catalytic residue"},
    "binding_sites":       {"Binding site", "Metal ion-binding site"},
    "ptm":                 {"Modified residue", "Phosphorylation", "Glycosylation",
                            "Acetylation", "Ubiquitination", "Methylation",
                            "Sumoylation", "Prenylation", "Palmitoylation",
                            "Myristoylation", "Nitrosylation", "Chromophore"},
    "structural_motifs":   {"Zinc finger", "Coiled-coil", "Leucine-rich repeat",
                            "Ankyrin repeat", "EF-hand", "Death domain",
                            "SH2 domain", "SH3 domain", "PDZ domain",
                            "WW domain", "HEAT repeat", "Arm repeat",
                            "Tetratricopeptide repeat", "Kelch repeat"},
    "topology":            {"Signal peptide", "Transmembrane region", "Chain",
                            "Peptide", "Propeptide", "Region"},
    "disulfide":           {"Disulfide bond"},
    "composition_bias":    {"Compositional bias", "Repeat", "Repeat CC"},
    "mutagenesis":         {"Mutagenesis"},
    "other":               set(),
}

for _cat, _types in list(_FEATURE_CATEGORIES.items()):
    if _cat != "other":
        _FEATURE_CATEGORIES["other"]  # ensure it exists


def _categorize_feature(ftype: str) -> str:
    for cat, types in _FEATURE_CATEGORIES.items():
        if cat == "other":
            continue
        if ftype in types:
            return cat
    return "other"


def _extract_feature_positions(f: dict) -> tuple[int | None, int | None]:
    loc = f.get("location", {}) or {}
    begin = loc.get("start", {}).get("value")
    end = loc.get("end", {}).get("value")
    return begin, end


def extract_features(raw: dict) -> dict:
    """Extract and categorize all UniProt features."""
    features = raw.get("features") or []
    result: dict[str, list[dict]] = {
        "active_sites": [],
        "binding_sites": [],
        "ptm": [],
        "structural_motifs": [],
        "topology": [],
        "disulfide": [],
        "composition_bias": [],
        "mutagenesis": [],
        "other": [],
    }

    for f in features:
        ftype = f.get("type", "")
        desc = f.get("description", "")
        begin, end = _extract_feature_positions(f)
        cat = _categorize_feature(ftype)
        entry = {
            "type": ftype,
            "description": desc,
            "begin": begin,
            "end": end,
        }
        if cat in result:
            result[cat].append(entry)
        else:
            result["other"].append(entry)

    return result


# ---------------------------------------------------------------------------
# 3. Functional Sites (active + binding + catalytic)
# ---------------------------------------------------------------------------

def extract_functional_sites(raw: dict) -> list[dict]:
    features = raw.get("features") or []
    sites = []
    for f in features:
        ftype = f.get("type", "")
        if ftype in ("Active site", "Catalytic residue", "Binding site",
                      "Metal ion-binding site"):
            begin, end = _extract_feature_positions(f)
            sites.append({
                "type": ftype,
                "description": f.get("description", ""),
                "begin": begin,
                "end": end,
                "amino_acid": f.get("aminoAcid", []),
            })
    return sites


# ---------------------------------------------------------------------------
# 4. Post-Translational Modifications
# ---------------------------------------------------------------------------

def extract_ptms(raw: dict) -> list[dict]:
    features = raw.get("features") or []
    ptms = []
    ptm_types = {
        "Modified residue", "Phosphorylation", "Glycosylation",
        "Acetylation", "Ubiquitination", "Methylation",
        "Sumoylation", "Prenylation", "Palmitoylation",
        "Myristoylation", "Nitrosylation", "Chromophore",
        "Lipidation", "Deamidation", "Hydroxylation",
        "Iodination", "Sulfation",
    }
    for f in features:
        ftype = f.get("type", "")
        if ftype in ptm_types or "modif" in ftype.lower():
            begin, end = _extract_feature_positions(f)
            ptms.append({
                "type": ftype,
                "description": f.get("description", ""),
                "begin": begin,
                "end": end,
                "amino_acid": f.get("aminoAcid", []),
            })
    return ptms


# ---------------------------------------------------------------------------
# 5. Topology (signal peptides, TM regions, chains, propeptides)
# ---------------------------------------------------------------------------

def extract_topology(raw: dict) -> list[dict]:
    features = raw.get("features") or []
    topo = []
    topo_types = {"Signal peptide", "Transmembrane region", "Chain",
                  "Peptide", "Propeptide", "Signal", "Initiator methionine"}
    for f in features:
        ftype = f.get("type", "")
        if ftype in topo_types:
            begin, end = _extract_feature_positions(f)
            topo.append({
                "type": ftype,
                "description": f.get("description", ""),
                "begin": begin,
                "end": end,
            })
    return topo


# ---------------------------------------------------------------------------
# 6. Structural Motifs (zinc fingers, coiled coils, repeats, domains)
# ---------------------------------------------------------------------------

def extract_structural_motifs(raw: dict) -> list[dict]:
    features = raw.get("features") or []
    motifs = []
    motif_types = {
        "Zinc finger", "Coiled-coil", "Leucine-rich repeat",
        "Ankyrin repeat", "EF-hand", "Death domain",
        "SH2 domain", "SH3 domain", "PDZ domain",
        "WW domain", "HEAT repeat", "Arm repeat",
        "Tetratricopeptide repeat", "Kelch repeat",
        "Immunoglobulin-like domain", "Fibronectin type-III domain",
        "EGF-like domain", "Cadherin domain", "Laminin G domain",
        "G-patch domain", "PAC motif", "BTB domain",
        "MATH domain", "Bromodomain", "Chromodomain",
        "PH domain", "FYVE domain", "PX domain",
        "C1 domain", "C2 domain", "DEATH domain",
        "CARD domain", "DD domain", "DED domain",
        "RAF-like domain", "Ras-binding domain",
    }
    for f in features:
        ftype = f.get("type", "")
        if ftype in motif_types:
            begin, end = _extract_feature_positions(f)
            motifs.append({
                "type": ftype,
                "description": f.get("description", ""),
                "begin": begin,
                "end": end,
            })
    return motifs


# ---------------------------------------------------------------------------
# 7. Mutagenesis & Disease Variants
# ---------------------------------------------------------------------------

def extract_variants(raw: dict) -> list[dict]:
    features = raw.get("features") or []
    variants = []
    for f in features:
        ftype = f.get("type", "")
        if ftype in ("Mutagenesis", "Natural variant"):
            begin, end = _extract_feature_positions(f)
            variants.append({
                "type": ftype,
                "description": f.get("description", ""),
                "begin": begin,
                "end": end,
                "amino_acid": f.get("aminoAcid", []),
            })
    return variants


# ---------------------------------------------------------------------------
# 8. Disulfide Bonds
# ---------------------------------------------------------------------------

def extract_disulfide_bonds(raw: dict) -> list[dict]:
    features = raw.get("features") or []
    bonds = []
    for f in features:
        if f.get("type") == "Disulfide bond":
            begin, end = _extract_feature_positions(f)
            bonds.append({
                "begin": begin,
                "end": end,
                "description": f.get("description", ""),
            })
    return bonds


# ---------------------------------------------------------------------------
# 9. Composition Bias (low complexity, repeats)
# ---------------------------------------------------------------------------

def extract_composition_bias(raw: dict) -> list[dict]:
    features = raw.get("features") or []
    bias = []
    for f in features:
        ftype = f.get("type", "")
        if ftype in ("Compositional bias", "Repeat", "Repeat CC",
                      "Simple sequence", "Low complexity"):
            begin, end = _extract_feature_positions(f)
            bias.append({
                "type": ftype,
                "description": f.get("description", ""),
                "begin": begin,
                "end": end,
            })
    return bias


# ---------------------------------------------------------------------------
# 10. Gene Ontology Annotations
# ---------------------------------------------------------------------------

def extract_go_terms(raw: dict) -> list[dict]:
    refs = raw.get("uniProtKBCrossReferences") or []
    go_terms = []
    for r in refs:
        if r.get("database") == "GO":
            term_id = r.get("id", "")
            props = r.get("properties") or []
            term_text = props[0].get("value", "") if props else ""
            category = ""
            if "F:" in term_text:
                category = "molecular_function"
            elif "P:" in term_text:
                category = "biological_process"
            elif "C:" in term_text:
                category = "cellular_component"
            go_terms.append({
                "id": term_id,
                "term": term_text,
                "category": category,
            })
    return go_terms


# ---------------------------------------------------------------------------
# 11. Pathway Annotations (KEGG, Reactome)
# ---------------------------------------------------------------------------

def extract_pathways(raw: dict) -> list[dict]:
    refs = raw.get("uniProtKBCrossReferences") or []
    pathways = []
    for r in refs:
        db = r.get("database", "")
        if db in ("KEGG", "Reactome", "WikiPathways"):
            pathway_id = r.get("id", "")
            props = r.get("properties") or []
            name = ""
            for p in props:
                if p.get("key") == "Pathway name":
                    name = p.get("value", "")
                    break
            if not name and props:
                name = props[0].get("value", "")
            pathways.append({
                "database": db,
                "id": pathway_id,
                "name": name,
            })
    return pathways


# ---------------------------------------------------------------------------
# 12. Combined Analysis (all features at once)
# ---------------------------------------------------------------------------

async def full_analysis(accession: str) -> dict:
    """Run all domain/motif analyses for a UniProt accession."""
    accession = _sanitize(accession)
    raw = await fetch_uniprot_raw(accession)

    interpro = await fetch_interpro_domains(accession)
    features = extract_features(raw) if raw else {}
    functional_sites = extract_functional_sites(raw) if raw else []
    ptms = extract_ptms(raw) if raw else []
    topology = extract_topology(raw) if raw else []
    motifs = extract_structural_motifs(raw) if raw else []
    variants = extract_variants(raw) if raw else []
    disulfide = extract_disulfide_bonds(raw) if raw else []
    composition = extract_composition_bias(raw) if raw else []
    go_terms = extract_go_terms(raw) if raw else []
    pathways = extract_pathways(raw) if raw else []

    seq_len = (raw.get("sequence", {}) or {}).get("length", 0)
    seq = (raw.get("sequence", {}) or {}).get("value", "")
    organism = ((raw.get("organism", {}) or {}).get("scientificName", ""))
    protein_name = ""
    desc = raw.get("proteinDescription", {}) or {}
    rec = desc.get("recommendedName", {}) or {}
    protein_name = (rec.get("fullName", {}) or {}).get("value", "")

    return {
        "accession": accession,
        "protein_name": protein_name,
        "organism": organism,
        "sequence_length": seq_len,
        "sequence": seq,
        "domains": interpro.get("domains", []),
        "active_sites": functional_sites,
        "ptms": ptms,
        "topology": topology,
        "structural_motifs": motifs,
        "variants": variants,
        "disulfide_bonds": disulfide,
        "composition_bias": composition,
        "go_terms": go_terms,
        "pathways": pathways,
        "feature_summary": {
            cat: len(items) for cat, items in features.items() if items
        },
    }
