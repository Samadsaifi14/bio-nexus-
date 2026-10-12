"""Read-only scientific validation registry endpoint."""

from fastapi import APIRouter

from app.science.validation_registry import get_validation_registry

router = APIRouter(prefix="/api/scientific-validation", tags=["scientific-validation"])


@router.get("")
async def scientific_validation_registry():
    return get_validation_registry()
