"""Structure export endpoints — techspec.md §2.

Downloads for AlphaFold / RCSB structures: PDB, CIF, and a real PyMOL session
(.pse) with cartoon + pLDDT spectrum pre-applied. ChimeraX/VMD are served as
the preferred coordinate format only; the matching command scripts are generated
client-side (see StructureExportMenu.tsx) because .cxs/.vmd state files cannot
be scripted headlessly with the open-source wheel.
"""

import logging
import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.services.auth import require_user_id
from app.services.ssrf import validate_url
from app.tools.structure_prep import (
    validate_pdb_id,
    validate_uniprot_accession,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/structure-export", tags=["structure_export"])

ALPHAFOLD_FILES = "https://alphafold.ebi.ac.uk/files"
RCSB_DOWNLOAD = "https://files.rcsb.org/download"

_FORMATS = {"pdb": "pdb", "cif": "cif"}


def _resolve_source(identifier: str) -> tuple[str, str, str]:
    """Map an identifier to (url_base_kind, validated_id, human_label)."""
    ident = identifier.strip()
    try:
        acc = validate_uniprot_accession(ident)
        return ("alphafold", acc, f"AF_{acc}")
    except ValueError:
        pass
    try:
        pdb_id = validate_pdb_id(ident)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ("rcsb", pdb_id, pdb_id)


def _source_url(kind: str, ident: str, fmt: str) -> str:
    if kind == "alphafold":
        return f"{ALPHAFOLD_FILES}/AF_{ident}-F1-model_v4.{fmt}"
    return f"{RCSB_DOWNLOAD}/{ident}.{fmt}"


async def _fetch_text(url: str) -> str:
    validate_url(url)
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        res = await client.get(url)
    if res.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail=f"No structure file found at {url} — this entry may have no model.",
        )
    res.raise_for_status()
    return res.text


def _build_pse(pdb_text: str, name: str) -> bytes:
    """Create a PyMOL session pre-styled with cartoon + pLDDT spectrum."""
    import pymol2

    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = Path(tmpdir) / "input.pdb"
        out_path = Path(tmpdir) / "session.pse"
        in_path.write_text(pdb_text)

        with pymol2.PyMOL() as p:
            p.cmd.load(str(in_path), "struct")
            p.cmd.hide("everything")
            p.cmd.show("cartoon")
            # B-factor column carries pLDDT in AF models → rainbow spectrum
            p.cmd.spectrum("b", "rainbow", selection="struct")
            p.cmd.bg_color("white")
            p.cmd.set("ray_opaque_background", 0)
            p.cmd.save(str(out_path), "struct")

        data = out_path.read_bytes()

    if len(data) < 100:
        raise RuntimeError("pymol2 produced an empty session file")
    logger.info("Built PyMOL session %s (%d bytes)", name, len(data))
    return data


@router.get("/structure/{identifier}")
async def export_structure(
    identifier: str,
    format: str = "pdb",
    user_id: str = Depends(require_user_id),
):
    """Download a structure as PDB, mmCIF, or a styled PyMOL session (.pse)."""
    fmt = format.lower().strip()
    if fmt not in _FORMATS and fmt != "pse":
        raise HTTPException(status_code=400, detail="format must be one of: pdb, cif, pse")

    kind, ident, label = _resolve_source(identifier)

    try:
        text = await _fetch_text(_source_url(kind, ident, _FORMATS.get(fmt, "pdb")))
    except httpx.HTTPStatusError as exc:
        logger.warning("Structure fetch failed for %s (%s): %s", identifier, fmt, exc)
        raise HTTPException(status_code=502, detail="Upstream structure service failed") from exc

    if fmt == "pse":
        try:
            data = _build_pse(text, label)
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="PyMOL session export is unavailable on this deployment",
            ) from exc
        except Exception as exc:
            logger.exception("PyMOL session build failed for %s", identifier)
            raise HTTPException(status_code=500, detail="Failed to build PyMOL session") from exc
        return Response(
            content=data,
            media_type="chemical/x-pymol-session",
            headers={"Content-Disposition": f'attachment; filename="{label}_styled.pse"'},
        )

    media = "chemical/x-pdb" if fmt == "pdb" else "chemical/x-mmcif"
    return Response(
        content=text,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{label}.{fmt}"'},
    )
