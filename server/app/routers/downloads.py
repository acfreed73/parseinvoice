from fastapi import APIRouter, File, UploadFile, HTTPException
import subprocess
import sqlite3
import shutil
import json
from fastapi.responses import FileResponse
from pathlib import Path
import csv
from datetime import datetime
import pandas as pd

from server.app.utils import clean_json_output

router = APIRouter()

UPLOAD_DIR = Path("data/pdfs")
TEXT_DIR = Path("data/text")
UNPROCESSED_DIR = Path("data/unprocessed")
TEMPLATE_DIR = Path("data/templates")
DB_PATH = Path("data/invoices.db")

OUTPUT_DIR = Path("data/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

field_mapping = {
    "invoice_number": "Invoice Number",
    "amount": "Amount",
    "date": "Date",
    "due_date": "Due Date",
    "terms": "Terms",
    "sold_to": "Sold To",
    "bill_to": "Mail To",
}

columns_order = ["File"] + list(dict.fromkeys(field_mapping.values()))

for directory in [UPLOAD_DIR, TEXT_DIR, UNPROCESSED_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

@router.post("/upload/")
async def upload_pdf(file: UploadFile = File(...)):
    """Handles PDF file upload and automatically triggers processing."""
    file_path = UPLOAD_DIR / file.filename

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    # Process the file automatically
    result = subprocess.run(
        ["invoice2data", "--template-folder", str(TEMPLATE_DIR), "--output-format", "json", str(file_path)],
        capture_output=True, text=True
    )

    print("Processing Output:", result.stdout)  # ✅ Debugging Processing
    print("Processing Error:", result.stderr)   # ✅ Capture Errors
    # Extract JSON from log output
    json_data = clean_json_output(result.stderr)
    print("JSON Data:", json_data)

    if "No template" in result.stderr:  # ❌ Processing failed
        unprocessed_path = UNPROCESSED_DIR / file.filename
        shutil.move(file_path, unprocessed_path)  # Move failed file to unprocessed folder
        return {"message": f"Upload successful, but no matching template for {file.filename}. Moved to unprocessed.", "status": "failed"}

    json_data = result.stderr.strip()
    if not json_data:
        unprocessed_path = UNPROCESSED_DIR / file.filename
        shutil.move(file_path, unprocessed_path)  # Move failed file to unprocessed folder
        return {"message": f"Upload successful, but processing failed for {file.filename}. Moved to unprocessed.", "status": "failed"}
    json_string = json.dumps(json_data, indent=2)
    # Store in database
    try:
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO invoices (filename, json_data) VALUES (?, ?)", (file.filename, json_string))
        conn.commit()
    except sqlite3.OperationalError as e:
        unprocessed_path = UNPROCESSED_DIR / file.filename
        shutil.move(file_path, unprocessed_path)  # Move failed file to unprocessed folder
        return {"message": f"Database error: {e}. Moved to unprocessed.", "status": "failed"}
    finally:
        conn.close()

    return {"message": f"File uploaded and processed successfully", "filename": file.filename, "status": "success"}
@router.get("/download/json/")
async def download_json():
    """Download processed invoices as JSON."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename, json_data FROM invoices")
    results = c.fetchall()
    conn.close()

    invoices = {row[0]: json.loads(row[1]) for row in results}
    json_path = OUTPUT_DIR / "invoices.json"

    with open(json_path, "w") as json_file:
        json.dump(invoices, json_file, indent=2)

    return FileResponse(json_path, media_type="application/json", filename="invoices.json")


@router.get("/download/csv/")
async def download_csv():
    """Download processed invoices as CSV."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename, json_data FROM invoices")
    results = c.fetchall()
    conn.close()

    if not results:
        return {"message": "No processed invoices found."}

    invoices = []
    for row in results:
        if row[1] is None:
            continue
        try:
            invoices.append(json.loads(row[1]))
        except json.JSONDecodeError:
            continue

    if not invoices:
        return {"message": "No valid invoice data found."}

    fieldnames = set()
    for invoice in invoices:
        fieldnames.update(invoice.keys())

    csv_filename = f"invoices_{datetime.today().strftime('%m-%d-%Y')}.csv"
    csv_path = OUTPUT_DIR / csv_filename

    with open(csv_path, "w", newline="") as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=["filename"] + list(fieldnames))
        csv_writer.writeheader()
        for row, invoice_data in zip(results, invoices):
            invoice_data["filename"] = row[0]
            csv_writer.writerow(invoice_data)

    return FileResponse(csv_path, media_type="text/csv", filename=csv_filename)

@router.get("/download/xls/")
async def download_xlsx():
    print("Test")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename, json_data FROM invoices")
    results = c.fetchall()
    conn.close()

    if not results:
        return {"message": "No processed invoices found."}

    invoices = []
    for row in results:
        if row[1] is None:
            continue
        try:
            invoices.append((row[0], json.loads(row[1])))
        except json.JSONDecodeError:
            continue

    if not invoices:
        return {"message": "No valid invoice data found."}

    formatted_data = []
    for filename, invoice in invoices:
        row = {"File": filename}
        for key, col_name in field_mapping.items():
            value = invoice.get(key, "")
            if isinstance(value, str):
                if col_name == "Mail To" and "innovationdiagnostics" in value.lower():
                    value = "Innovation Diagnostics"
                elif any(c in value for c in "-/") and len(value) >= 8:
                    try:
                        dt = datetime.strptime(value.strip(), "%Y-%m-%d")
                        value = dt.strftime("%m/%d/%Y")
                    except Exception:
                        pass
            row[col_name] = value
        formatted_data.append(row)

    df = pd.DataFrame(formatted_data)[columns_order]

    xlsx_filename = f"invoices_summary_{datetime.today().strftime('%Y%m%d')}.xlsx"
    xlsx_path = OUTPUT_DIR / xlsx_filename
    df.to_excel(xlsx_path, index=False)

    return FileResponse(xlsx_path, media_type="text/xls", filename=xlsx_filename)
    # return FileResponse(xlsx_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=xlsx_filename)