"""GEO analysis endpoints (single implementation — see app.services.geo)."""

from typing import Dict, Optional

from fastapi import APIRouter

from app.services import geo as geo_service

router = APIRouter(prefix="/api/geo", tags=["geo"])


@router.get("/series/{gse}")
async def get_series(gse: str) -> Dict[str, object]:
    """Resolve a GSE to series metadata + sample list."""
    geo_service._validate_gse(gse)
    return await geo_service.resolve_series(gse)


@router.get("/series/{gse}/files")
async def get_supplementary_files(gse: str) -> Dict[str, object]:
    """List every supplementary file for the GSE (with sizes)."""
    geo_service._validate_gse(gse)
    return await geo_service.list_supplementary_files(gse)


@router.get("/series/{gse}/files/{filename}")
async def download_file(gse: str, filename: str):
    """Stream a GEO supplementary file through unchanged (no size cap)."""
    geo_service._validate_gse(gse)
    geo_service._validate_filename(filename)
    return await geo_service.stream_geo_file(gse, filename)