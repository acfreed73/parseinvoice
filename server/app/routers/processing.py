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

REQUIRED_FIELDS = ["invoice_number", "amount", "date", "customer", "vendor"]

def try_parse_date(date_str):
    formats = [
        "%d %B %Y", "%d-%b-%Y", "%B %d, %Y", "%b %d, %Y",
        "%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def auto_select_template(filename: str) -> str:
    lowercase_name = filename.lower()
    for template_file in TEMPLATE_RAW_DIR.glob("*.yml"):
        with open(template_file, "r") as f:
            tpl = yaml.safe_load(f)
            issuer = tpl.get("issuer", "").lower()
            if issuer and issuer in lowercase_name:
                return template_file.name
    return None

def process_with_pdftotext(filename: str, template_name: str, srcPDFS: str) -> dict:
    raw_result = subprocess.run(["pdftotext", "-raw", f"data/{srcPDFS}/{filename}", "-"], capture_output=True, text=True)
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

    for date_field in ["date", "due_date"]:
        if date_field in extracted:
            parsed_date = try_parse_date(extracted[date_field])
            if parsed_date:
                extracted[date_field] = parsed_date.strftime("%-m/%-d/%Y")

    if "issuer" not in extracted:
        extracted["issuer"] = template.get("issuer")
    extracted["desc"] = f"Invoice from {extracted['issuer']}"
    extracted["currency"] = template.get("options", {}).get("currency", "USD")

    # Map legacy field names to new ones
    if "sold_to" in extracted:
        extracted["customer"] = extracted.pop("sold_to")
    if "bill_to" in extracted:
        extracted["vendor"] = extracted.pop("bill_to")

    missing = [field for field in REQUIRED_FIELDS if field not in extracted or not extracted[field]]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    return extracted

@router.post("/process/{filename}")
async def process_single_invoice(filename: str, pdftotext: bool = Query(False), template: str = Query(None)):
    pdf_file = UPLOAD_DIR / filename

    if not pdf_file.exists():
        pdf_file = UNPROCESSED_DIR / filename
        if not pdf_file.exists():
            raise HTTPException(status_code=404, detail="File not found.")

    if pdftotext:
        if not template:
            template = auto_select_template(filename)
            if not template:
                return {"message": f"No template matched filename: {filename}", "status": "failed"}

        try:
            print(template)
            json_data = process_with_pdftotext(filename, template, srcPDFS="unprocessed")
            print("Extracted using pdftotext:", json.dumps(json_data, indent=2))
        except Exception as e:
            return {"message": f"pdftotext processing failed: {e}", "status": "failed", "template": template}

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
        processed_path = UPLOAD_DIR / filename
        if pdf_file.exists():
            shutil.move(pdf_file, processed_path)

    return {"message": f"Successfully processed {filename} (pdftotext: {pdftotext})", "status": "success", "template": template if pdftotext else None}
