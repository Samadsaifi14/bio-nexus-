from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
from app.config import settings
from app.models.responses import WaitlistResponse

router = APIRouter()


class WaitlistEntry(BaseModel):
    email: str


@router.post("", response_model=WaitlistResponse)
async def join_waitlist(entry: WaitlistEntry):
    url = f"{settings.SUPABASE_URL}/rest/v1/waitlist"
    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json={"email": entry.email})
        if resp.status_code == 409:
            raise HTTPException(status_code=409, detail="Already on waitlist")
        if resp.status_code >= 400:
            raise HTTPException(status_code=500, detail=resp.text)
        return {"status": "added", "email": entry.email}
