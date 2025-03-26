from fastapi import APIRouter, HTTPException, Request
from pathlib import Path
from pydantic import BaseModel
from typing import List
import yaml

router = APIRouter()

TEMPLATE_DIR = Path("data/templates")
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

class Annotation(BaseModel):
    text: str
    type: str  # "issuer", "keyword", "exclude_keyword", "field"

class TemplateSaveRequest(BaseModel):
    pdf_name: str
    annotations: List[Annotation]

@router.get("/")
async def get_templates():
    """List all available templates."""
    templates = [f.name for f in TEMPLATE_DIR.glob("*.yml")]
    return {"templates": templates}

@router.get("/load/{pdf_name}")
async def load_template(pdf_name: str):
    """Load a saved template."""
    template_path = TEMPLATE_DIR / f"{pdf_name}.yml"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")

    with open(template_path, "r") as f:
        template_data = yaml.safe_load(f)

    return template_data

@router.post("/save/")
async def save_template(request: Request):
    """Save a new template."""
    data = await request.json()
    try:
        request_data = TemplateSaveRequest(**data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid request: {str(e)}")

    template_path = TEMPLATE_DIR / f"{request_data.pdf_name}.yml"
    template_data = {
        "issuer": None,
        "keywords": [],
        "exclude_keywords": [],
        "fields": {},
    }

    for ann in request_data.annotations:
        if ann.type == "issuer":
            template_data["issuer"] = ann.text
        elif ann.type == "keyword":
            template_data["keywords"].append(ann.text)
        elif ann.type == "exclude_keyword":
            template_data["exclude_keywords"].append(ann.text)
        elif ann.type == "field":
            template_data["fields"][ann.text] = r"([\d\-.]+)"

    with open(template_path, "w") as f:
        yaml.dump(template_data, f, default_flow_style=False)

    return {"message": "Template saved successfully", "template": template_path.name}
