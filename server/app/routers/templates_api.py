from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pathlib import Path
from pydantic import BaseModel
from typing import List
import yaml
import subprocess

router = APIRouter()

TEMPLATE_DIR = Path("data/templates")  # ✅ YAML Templates
UPLOAD_DIR = Path("data/template_uploads")  # ✅ Uploaded PDFs for Template Builder
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

class Annotation(BaseModel):
    text: str
    type: str  # "issuer", "keyword", "exclude_keyword", "field", "option", "line"

class TemplateSaveRequest(BaseModel):
    pdf_name: str
    annotations: List[Annotation]

@router.get("/")
async def get_templates():
    templates = [f.name for f in TEMPLATE_DIR.glob("*.yml")]
    return {"templates": templates}

@router.get("/load/{pdf_name}")
async def load_template(pdf_name: str):
    template_path = TEMPLATE_DIR / f"{pdf_name}.yml"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")

    with open(template_path, "r") as f:
        template_data = yaml.safe_load(f)

    return template_data

@router.post("/save/")
async def save_template(request: Request):
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
        "options": {"currency": "USD", "date_formats": ["%m/%d/%Y"]},
        "lines": []
    }

    for ann in request_data.annotations:
        if ann.type == "issuer":
            template_data["issuer"] = ann.text
        elif ann.type == "keyword":
            template_data["keywords"].append(ann.text)
        elif ann.type == "exclude_keyword":
            template_data["exclude_keywords"].append(ann.text)
        elif ann.type == "field":
            template_data["fields"][ann.text] = r"([\d\-.,\s]+)"
        elif ann.type == "option":
            template_data["options"][ann.text] = "Configured"
        elif ann.type == "line":
            template_data["lines"].append(ann.text)

    with open(template_path, "w") as f:
        yaml.dump(template_data, f, default_flow_style=False)

    return {"message": "Template saved successfully", "template": template_path.name}

# ✅ **NEW: Extract Text from PDF for Template Builder**
@router.post("/extract/")
async def extract_text_from_pdf(file: UploadFile = File(...)):
    """Extracts text from a PDF and returns it for annotation."""
    file_path = UPLOAD_DIR / file.filename

    # ✅ Save uploaded file
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    # ✅ Extract text using pdftotext
    result = subprocess.run(
        ["pdftotext", "-layout", str(file_path), "-"],
        capture_output=True,
        text=True
    )

    extracted_text = result.stdout.strip()

    # ✅ Handle extraction failures
    if not extracted_text:
        raise HTTPException(
            status_code=400,
            detail=f"PDF '{file.filename}' appears to be an image-based file. Please run OCR before uploading."
        )
    return {"filename": file.filename, "text": extracted_text}
