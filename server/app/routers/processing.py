import json
import shutil
import subprocess
import sqlite3
import re
import yaml
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime

from server.app.utils import clean_json_output

router = APIRouter()

UPLOAD_DIR = Path("data/pdfs")
UNPROCESSED_DIR = Path("data/unprocessed")
TEMPLATE_DIR = Path("data/templates")
TEMPLATE_RAW_DIR = Path("data/templates_raw")
DB_PATH = Path("data/invoices.db")

def process_with_pdftotext(filename: str, template_name: str) -> dict:
    raw_result = subprocess.run(["pdftotext", "-raw", f"data/unprocessed/{filename}", "-"], capture_output=True, text=True)
    text = raw_result.stdout

    template_path = TEMPLATE_RAW_DIR / template_name
    if not template_path.exists():
        raise ValueError(f"Template {template_name} not found.")

    with open(template_path, "r") as f:
        template = yaml.safe_load(f)

    extracted = {}
    for field, pattern in template.get("fields", {}).items():
        match = re.search(pattern, text)
        if match:
            extracted[field] = match.group(1).strip()

    # Format date fields
    for date_field in ["date", "due_date"]:
        if date_field in extracted:
            try:
                dt = datetime.strptime(extracted[date_field], "%b %d, %Y")
                extracted[date_field] = dt.strftime("%-m/%-d/%Y")  # Use "%m/%d/%Y" on Windows
            except ValueError:
                pass  # Keep original if format parsing fails

    if "issuer" not in extracted:
        extracted["issuer"] = template.get("issuer")
    extracted["desc"] = f"Invoice from {extracted['issuer']}"
    extracted["currency"] = template.get("options", {}).get("currency", "USD")

    return extracted

@router.post("/process/{filename}")
async def process_single_invoice(filename: str, pdftotext: bool = Query(False), template: str = Query(None)):
    """Processes a single uploaded PDF using invoice2data or pdftotext fallback."""
    pdf_file = UPLOAD_DIR / filename

    if not pdf_file.exists():
        pdf_file = UNPROCESSED_DIR / filename
        if not pdf_file.exists():
            raise HTTPException(status_code=404, detail="File not found.")

    if pdftotext:
        if not template:
            raise HTTPException(status_code=400, detail="Template must be provided when using pdftotext mode.")

        try:
            json_data = process_with_pdftotext(filename, template)
            print("Extracted using pdftotext:", json.dumps(json_data, indent=2))
        except Exception as e:
            return {"message": f"pdftotext processing failed: {e}", "status": "failed"}

    else:
        result = subprocess.run(
            ["invoice2data", "--template-folder", str(TEMPLATE_DIR), "--output-format", "json", str(pdf_file)],
            capture_output=True, text=True
        )

        print("Raw invoice2data output:", result.stdout)
        print("Error (if any):", result.stderr)

        json_data = clean_json_output(result.stderr)

        if "No template" in result.stderr or not json_data:
            unprocessed_path = UNPROCESSED_DIR / filename
            shutil.move(pdf_file, unprocessed_path)
            return {"message": f"Processing failed for {filename}. Moved to unprocessed folder.", "status": "failed"}

    # Save result to DB
    json_string = json.dumps(json_data, indent=2)
    try:
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO invoices (filename, json_data) VALUES (?, ?)", (filename, json_string))
        conn.commit()
    except sqlite3.OperationalError as e:
        return {"message": f"Database error: {e}"}
    finally:
        conn.close()
        # ✅ Move processed file to 'pdfs'
        processed_path = UPLOAD_DIR / filename
        if pdf_file.exists():
            shutil.move(pdf_file, processed_path)

    return {"message": f"Successfully processed {filename} (pdftotext: {pdftotext})"}
