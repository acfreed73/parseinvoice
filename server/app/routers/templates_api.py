from fastapi import APIRouter, HTTPException, UploadFile, File
from pathlib import Path
from pydantic import BaseModel
from typing import List
import yaml
import shutil


router = APIRouter()

TEMPLATE_DIR = Path("server/static/templates")  # Change path to serve from /static/templates
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

class Annotation(BaseModel):
    field: str
    x: int
    y: int
    width: int
    height: int

class TemplateRequest(BaseModel):
    pdf_name: str
    annotations: list[Annotation]

class TemplateSaveRequest(BaseModel):
    pdf_name: str
    annotations: List[Annotation]
    
@router.get("/")
async def get_templates():
    """List all available templates"""
    templates = [f.name for f in TEMPLATE_DIR.glob("*.yml")]
    return {"templates": templates}

@router.get("/load/{pdf_name}")
async def load_template(pdf_name: str):
    """Load saved template data"""
    template_path = TEMPLATE_DIR / f"{pdf_name}.yml"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")

    with open(template_path, "r") as f:
        template_data = yaml.safe_load(f)

    return template_data
@router.post("/upload_template/")
async def upload_template(file: UploadFile = File(...)):
    """Uploads a template PDF to the static directory for viewing."""
    file_path = TEMPLATE_DIR / file.filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"message": "Template uploaded successfully", "filename": file.filename}
