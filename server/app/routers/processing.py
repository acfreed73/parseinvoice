import json
from fastapi import APIRouter, HTTPException
import subprocess
import sqlite3
from pathlib import Path

from server.app.utils import clean_json_output

router = APIRouter()

UPLOAD_DIR = Path("data/pdfs")
UNPROCESSED_DIR = Path("data/unprocessed")
TEMPLATE_DIR = Path("data/templates")
DB_PATH = Path("data/invoices.db")

@router.post("/process/{filename}")
async def process_single_invoice(filename: str):
    """Processes a single uploaded PDF using invoice2data."""
    pdf_file = UPLOAD_DIR / filename

    if not pdf_file.exists():
        pdf_file = UNPROCESSED_DIR / filename
        if not pdf_file.exists():
            raise HTTPException(status_code=404, detail="File not found.")

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

    return {"message": f"Successfully processed {filename}"}
