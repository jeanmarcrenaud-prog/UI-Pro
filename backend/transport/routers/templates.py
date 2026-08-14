"""Templates router — list and apply project templates."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.domain.core.templates import apply_template, list_templates

router = APIRouter(prefix="/api", tags=["templates"])


class TemplateInfo(BaseModel):
    id: str
    name: str
    description: str


class ApplyTemplateRequest(BaseModel):
    template_id: str
    workspace: str | None = None


class ApplyTemplateResponse(BaseModel):
    success: bool
    template_id: str
    files_written: list[str]
    errors: list[str]


@router.get("/templates", response_model=list[TemplateInfo])
async def get_templates():
    """List all available project templates."""
    return list_templates()


@router.post("/templates/{template_id}/apply", response_model=ApplyTemplateResponse)
async def apply_template_endpoint(template_id: str, request: ApplyTemplateRequest | None = None):
    """Apply a template by writing its files to the workspace."""
    workspace = request.workspace if request else None
    result = apply_template(template_id, workspace)
    if not result["success"]:
        raise HTTPException(
            status_code=404 if "not found" in result["errors"][0] else 500,
            detail=result["errors"][0],
        )
    return ApplyTemplateResponse(**result)
