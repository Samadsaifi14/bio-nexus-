from pydantic import BaseModel
from typing import Any, Optional


class PipelineRunResponse(BaseModel):
    job_id: str
    status: str


class PipelineDefinitionResponse(BaseModel):
    pipelines: list[dict[str, Any]]


class JobCountResponse(BaseModel):
    count: int
    limit: int
    remaining: int


class JobDeleteResponse(BaseModel):
    status: str


class InterpretResponse(BaseModel):
    prompt: str
    context_size: int


class WaitlistResponse(BaseModel):
    status: str
    email: str


class ProfileUpdateResponse(BaseModel):
    status: str
    data: Optional[dict[str, Any]] = None


class ErrorResponse(BaseModel):
    detail: str
