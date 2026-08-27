"""Tool cards API — machine-readable manifest of all platform tools."""

from fastapi import APIRouter
from app.tools.tool_cards import get_tool_cards, get_tool_card

router = APIRouter()


@router.get("")
async def list_tool_cards():
    return {"tools": get_tool_cards()}


@router.get("/{tool_id}")
async def get_tool_card_detail(tool_id: str):
    card = get_tool_card(tool_id)
    if not card:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Tool card not found: {tool_id}")
    return card
