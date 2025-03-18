import csv
import re
import shutil
import string
import subprocess
import sqlite3
import json
import os
import yaml
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pathlib import Path
from pydantic import BaseModel
from typing import List, Dict

from server.app.routers import templates_api

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory="server/static"), name="static")
class Annotation(BaseModel):
    field: str
    type: str  # "issuer", "field", or "keyword"

class TemplateSaveRequest(BaseModel):
    pdf_name: str
    annotations: List[Annotation]

# Directories for storage
UPLOAD_DIR = Path("data/pdfs")
OUTPUT_DIR = Path("data/output")
TEMPLATE_DIR = Path("data/templates")
DB_PATH = Path("data/invoices.db")
UNPROCESSED_DIR = Path("data/unprocessed")

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
UNPROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Initialize database
conn = sqlite3.connect(DB_PATH, isolation_level=None)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY,
    filename TEXT UNIQUE,
    json_data TEXT,
    csv_data TEXT
)''')
conn.commit()
conn.close()

app.include_router(templates_api.router, prefix="/templates", tags=["Templates"])

# Setup Jinja2 templates
templates = Jinja2Templates(directory="server/templates")

@app.get("/")
async def home(request: Request):
    """Render the UI with a list of uploaded PDFs and their processing status."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get all filenames from the pdfs folder
    uploaded_files = [f.name for f in UPLOAD_DIR.glob("*.pdf")]

    # Check which PDFs have been processed
    c.execute("SELECT filename FROM invoices")
    processed_files = {row[0] for row in c.fetchall()}  # Convert to set for quick lookup
    conn.close()

    # Create file list with processing status
    files = [{"filename": f, "processed": f in processed_files} for f in uploaded_files]

    return templates.TemplateResponse("index.html", {"request": request, "files": files})

def sanitize_filename(filename):
    """Sanitize filenames by removing special characters and spaces."""
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
    sanitized = ''.join(c for c in filename if c in valid_chars)
    sanitized = sanitized.replace(" ", "_")  # Replace spaces with underscores
    return sanitized[:100]  # Limit length to avoid system errors

async def process_single_invoice(filename: str):
    """Processes a single uploaded PDF file."""
    pdf_file = UPLOAD_DIR / filename

    if not pdf_file.exists():
        return {"message": "Processing failed: File not found"}

    result = subprocess.run(
        ["invoice2data", "--template-folder", str(TEMPLATE_DIR), "--output-format", "json", str(pdf_file)],
        capture_output=True, text=True
    )

    json_data = clean_json_output(result.stderr)

    if not json_data:
        return {"message": f"Processing failed for {filename}"}

    json_string = json.dumps(json_data, indent=2)

    # Store JSON in the database
    try:
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO invoices (filename, json_data) VALUES (?, ?)", (filename, json_string))
        conn.commit()
        conn.close()
    except sqlite3.OperationalError as e:
        return {"message": f"Database error: {e}"}

    return {"message": f"Successfully processed {filename}"}
@app.get("/uploaded_files/")
async def get_uploaded_files():
    """Fetches the list of uploaded PDFs and their processing status."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get all filenames from the processed PDFs folder
    uploaded_files = [f.name for f in UPLOAD_DIR.glob("*.pdf")]

    # Get all unprocessed filenames from the unprocessed PDFs folder
    unprocessed_files = [f.name for f in UNPROCESSED_DIR.glob("*.pdf")]

    # Get processed files from the database
    c.execute("SELECT filename FROM invoices WHERE json_data IS NOT NULL")
    processed_files = {row[0] for row in c.fetchall()}  # Convert to a set for quick lookup
    conn.close()

    # Create file list with processing status
    files = []
    for f in uploaded_files + unprocessed_files:
        files.append({
            "filename": f,
            "processed": f in processed_files,
            "unprocessed": f in unprocessed_files
        })

    return JSONResponse(content={"files": files})
@app.post("/upload/")
async def upload_pdf(file: UploadFile = File(...)):
    """Handles file upload and moves failed PDFs to 'Unprocessed PDFs'."""
    sanitized_filename = sanitize_filename(file.filename)
    file_path = UPLOAD_DIR / sanitized_filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Try to process the file
    process_result = await process_single_invoice(sanitized_filename)

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    c = conn.cursor()

    if process_result["message"].startswith("Processing failed"):
        # Move file to "Unprocessed PDFs"
        unprocessed_path = UNPROCESSED_DIR / sanitized_filename
        shutil.move(file_path, unprocessed_path)

        # Store unprocessed file info in database
        c.execute(
            "INSERT OR IGNORE INTO invoices (filename, json_data, csv_data) VALUES (?, NULL, NULL)",
            (sanitized_filename,)
        )
        conn.commit()
        conn.close()
        return {
            "message": "File uploaded but failed to process. You can retry processing it later. It will be moved to the uploaded file in the menu Unprocessed PDFs.",
            "filename": sanitized_filename,
            "processed": False,
        }

    conn.close()
    return {
        "message": "File uploaded and processed successfully",
        "filename": sanitized_filename,
        "processed": True,
    }



def clean_json_output(stderr_text):
    """Extracts and formats valid JSON from invoice2data stderr output."""
    match = re.search(r"(\{.*\})", stderr_text, re.DOTALL)

    if not match:
        return None  # No valid JSON found

    raw_text = match.group(0)

    # Fix datetime issues
    raw_text = re.sub(
        r"datetime\.datetime\((\d{4}),\s*(\d{1,2}),\s*(\d{1,2}),\s*0,\s*0\)",
        r'"\1-\2-\3"',
        raw_text
    )

    raw_text = raw_text.replace("'", '"')

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return None

@app.post("/process/")
async def process_invoices():
    """Processes all PDFs in the upload directory and moves failed ones to 'unprocessed'."""
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    c = conn.cursor()

    for pdf_file in UPLOAD_DIR.glob("*.pdf"):
        print(f"📄 Processing file: {pdf_file.name}")

        result = subprocess.run(
            ["invoice2data", "--template-folder", str(TEMPLATE_DIR), "--output-format", "json", str(pdf_file)],
            capture_output=True, text=True
        )

        json_data = clean_json_output(result.stderr)

        if not json_data:
            print(f"❌ Error processing {pdf_file.name}: No valid JSON found. Moving to unprocessed queue.")

            # Move to Unprocessed PDFs folder
            unprocessed_path = Path("data/unprocessed") / pdf_file.name
            unprocessed_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(pdf_file, unprocessed_path)

            # Store in database with status "unprocessed"
            c.execute("INSERT OR REPLACE INTO invoices (filename, json_data, csv_data) VALUES (?, ?, ?)", 
                      (pdf_file.name, None, "unprocessed"))
            continue

        json_string = json.dumps(json_data, indent=2)

        print("\n✅ Extracted JSON:")
        print(json_string)

        # Store successful JSON result in database
        c.execute("INSERT OR REPLACE INTO invoices (filename, json_data, csv_data) VALUES (?, ?, ?)", 
                  (pdf_file.name, json_string, "processed"))

    conn.commit()
    conn.close()

    return {"message": "Processing completed."}
@app.get("/unprocessed/")
async def get_unprocessed_pdfs():
    """Retrieve the list of unprocessed PDFs."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename FROM invoices WHERE json_data IS NULL")
    unprocessed_files = [row[0] for row in c.fetchall()]
    conn.close()
    
    return {"unprocessed_files": unprocessed_files}

@app.post("/process/{filename}")
async def process_single_invoice(filename: str):
    """Processes a single uploaded PDF file."""

    # Check if the file exists in the processed folder
    pdf_file = UPLOAD_DIR / filename

    # If not found, check in the unprocessed folder
    if not pdf_file.exists():
        pdf_file = UNPROCESSED_DIR / filename
        if not pdf_file.exists():
            raise HTTPException(status_code=404, detail="File not found.")

    print(f"📄 Reprocessing file: {pdf_file.name}")

    # Run invoice2data on the specific file
    result = subprocess.run(
        ["invoice2data", "--template-folder", str(TEMPLATE_DIR), "--output-format", "json", str(pdf_file)],
        capture_output=True, text=True
    )

    json_data = clean_json_output(result.stderr)

    if not json_data:
        print(f"❌ Error processing {pdf_file.name}: No valid JSON found.")
        return {"message": f"Processing failed for {filename}"}

    json_string = json.dumps(json_data, indent=2)

    print("\n✅ Extracted JSON:")
    print(json_string)

    # ✅ Move file from unprocessed to processed folder
    if pdf_file.parent == UNPROCESSED_DIR:
        new_path = UPLOAD_DIR / filename
        shutil.move(str(pdf_file), new_path)
        print(f"✅ Moved {filename} from Unprocessed to PDFs folder.")

    # ✅ Store JSON in the database
    try:
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        c = conn.cursor()

        c.execute("INSERT OR REPLACE INTO invoices (filename, json_data) VALUES (?, ?)", (filename, json_string))
        conn.commit()
        print(f"✅ Database updated: {filename} marked as processed.")
    except sqlite3.OperationalError as e:
        print(f"❌ Database error: {e}")
        return {"message": f"Database error: {e}"}
    finally:
        conn.close()

    return {"message": f"Successfully reprocessed {filename}"}


@app.get("/results/")
async def get_results():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename, json_data FROM invoices")
    results = c.fetchall()
    conn.close()

    return JSONResponse(content={"invoices": results})

@app.get("/download/json/")
async def download_json():
    """Download all processed invoices as a JSON file."""
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

@app.get("/download/csv/")
async def download_csv():
    """Download all processed invoices as a CSV file."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename, json_data FROM invoices")
    results = c.fetchall()
    conn.close()

    if not results:
        raise HTTPException(status_code=404, detail="No processed invoices found.")

    invoices = []
    for row in results:
        if row[1] is None:  # Skip if JSON data is missing
            continue
        try:
            invoices.append(json.loads(row[1]))
        except json.JSONDecodeError:
            continue  # Skip invalid JSON

    if not invoices:
        raise HTTPException(status_code=500, detail="No valid invoice data found.")

    # Extract field names dynamically
    fieldnames = set()
    for invoice in invoices:
        fieldnames.update(invoice.keys())

    csv_filename = f"invoices_{datetime.today().strftime('%m-%d-%Y')}.csv"
    csv_path = OUTPUT_DIR / csv_filename

    # Write CSV
    with open(csv_path, "w", newline="") as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=["filename"] + list(fieldnames))
        csv_writer.writeheader()
        for row, invoice_data in zip(results, invoices):
            invoice_data["filename"] = row[0]
            csv_writer.writerow(invoice_data)

    return FileResponse(csv_path, media_type="text/csv", filename=csv_filename)


    # Write CSV file
    with open(csv_path, "w", newline="") as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=["filename"] + fieldnames)
        csv_writer.writeheader()

        for row in results:
            if row[1]:  # Ignore NoneType values
                invoice_data = json.loads(row[1])
                invoice_data["filename"] = row[0]  # Include filename in CSV
                csv_writer.writerow(invoice_data)

    return FileResponse(csv_path, media_type="text/csv", filename=csv_filename)



@app.post("/reset/")
async def reset_data():
    """Deletes all processed invoices, uploaded PDFs, and output files, and resets the database."""
    try:
        for pdf_file in UPLOAD_DIR.glob("*"):
            pdf_file.unlink()

        for output_file in OUTPUT_DIR.glob("*"):
            output_file.unlink()

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM invoices")
        conn.commit()
        conn.close()

        return {"message": "Database, uploaded PDFs, and output files have been reset."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting data: {str(e)}")
@app.delete("/delete/{filename}")
async def delete_invoice(filename: str):
    """Deletes a single PDF and its associated output files and database record."""
    try:
        # Define possible file paths
        pdf_paths = [UPLOAD_DIR / filename, UNPROCESSED_DIR / filename]
        json_path = OUTPUT_DIR / f"{Path(filename).stem}.json"
        csv_path = OUTPUT_DIR / f"{Path(filename).stem}.csv"

        # Remove the PDF from whichever directory it exists in
        for pdf_path in pdf_paths:
            if pdf_path.exists():
                pdf_path.unlink()

        # Remove processed output files
        if json_path.exists():
            json_path.unlink()
        if csv_path.exists():
            csv_path.unlink()

        # Remove entry from database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM invoices WHERE filename = ?", (filename,))
        conn.commit()
        conn.close()

        return {"message": f"Deleted {filename} and associated data."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting {filename}: {str(e)}")
@app.post("/templates/save/")
async def save_template(request: Request):
    """Process and save template annotations in invoice2data YAML format"""
    data = await request.json()
    print("🔍 Received Payload:", data)  # Debugging

    try:
        request_data = TemplateSaveRequest(**data)  # Validate data
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid request: {str(e)}")

    # ✅ Define YAML file path
    template_path = TEMPLATE_DIR / f"{request_data.pdf_name}.yml"

    # ✅ Extract issuer, keywords, and fields
    issuer = None
    keywords = []
    fields = {}

    for ann in request_data.annotations:
        if ann.type == "issuer":
            issuer = ann.field  # First 'issuer' annotation becomes the issuer name
        elif ann.type == "keyword":
            keywords.append(ann.field)  # Collect all keyword annotations
        elif ann.type == "field":
            # ✅ Dynamically generate regex based on annotation name
            sanitized_field_name = ann.field.strip().replace("#", r"\#")  # Escape '#' if present
            fields[ann.field] = rf"{sanitized_field_name}:\s+([\d\-.,\s]+)"

    # ✅ Use filename as a keyword if no keywords are manually specified
    if not keywords:
        keywords.append(request_data.pdf_name.split('.')[0])

    # ✅ Build YAML data structure
    template_data = {
        "issuer": issuer if issuer else "Unknown",
        "keywords": keywords,
        "fields": fields,
        "options": {
            "currency": "USD",
            "date_formats": ["%m/%d/%Y"],
        }
    }

    # ✅ Save to YAML file
    try:
        with open(template_path, "w") as f:
            yaml.dump(template_data, f, default_flow_style=False)
        print(f"✅ Template saved: {template_path}")  # Log successful save
    except Exception as e:
        print(f"❌ Error writing YAML file: {e}")  # Log errors
        raise HTTPException(status_code=500, detail=f"Failed to save YAML file: {str(e)}")

    # ✅ Verify the file actually exists before responding
    if not os.path.exists(template_path):
        raise HTTPException(status_code=500, detail="YAML file was not created")

    return {
        "message": "Template saved successfully",
        "template": template_path.name,
        "path": str(template_path),
    }