from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pathlib import Path
import csv
import re
import shutil
import string
import subprocess
import sqlite3
import json
import os

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory="server/static"), name="static")

# Directories for storage
UPLOAD_DIR = Path("data/pdfs")
OUTPUT_DIR = Path("data/output")
TEMPLATE_DIR = Path("data/templates")
DB_PATH = Path("data/invoices.db")

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

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

@app.post("/upload/")
async def upload_pdf(file: UploadFile = File(...)):
    """Handles file upload and sanitizes the filename before saving."""
    sanitized_filename = sanitize_filename(file.filename)
    file_path = UPLOAD_DIR / sanitized_filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Automatically process the uploaded file
    await process_invoices()

    return {"message": "File uploaded and processed successfully", "filename": sanitized_filename}

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
    for pdf_file in UPLOAD_DIR.glob("*.pdf"):
        print(f"📄 Processing file: {pdf_file.name}")

        result = subprocess.run(
            ["invoice2data", "--template-folder", str(TEMPLATE_DIR), "--output-format", "json", str(pdf_file)],
            capture_output=True, text=True
        )

        json_data = clean_json_output(result.stderr)

        if not json_data:
            print(f"❌ Error processing {pdf_file.name}: No valid JSON found.")
            continue

        json_string = json.dumps(json_data, indent=2)

        print("\n✅ Extracted JSON:")
        print(json_string)

        try:
            conn = sqlite3.connect(DB_PATH, isolation_level=None)
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO invoices (filename, json_data) VALUES (?, ?)", (pdf_file.name, json_string))
        except sqlite3.OperationalError as e:
            print(f"❌ Database error: {e}")
        finally:
            c.close()
            conn.close()

    return {"message": "Processing completed."}
@app.post("/process/{filename}")
async def process_single_invoice(filename: str):
    """Processes a single uploaded PDF file."""
    pdf_file = UPLOAD_DIR / filename

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

    # Store JSON in the database
    try:
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO invoices (filename, json_data) VALUES (?, ?)", (filename, json_string))
        conn.commit()
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
    """Download all processed invoices as a CSV file with a sanitized template name."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename, json_data FROM invoices")
    results = c.fetchall()
    conn.close()

    if not results:
        raise HTTPException(status_code=404, detail="No processed invoices found.")

    # Extract template name (assuming first processed file's data contains issuer)
    first_invoice = json.loads(results[0][1])  # Convert JSON string to dict
    raw_template_name = first_invoice.get("issuer", "invoice_data")

    # Sanitize the template name for a safe filename
    template_name = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_template_name).strip("_")

    # Get today's date in MM-DD-YYYY format
    current_date = datetime.today().strftime("%m-%d-%Y")

    # Define CSV filename format
    csv_filename = f"{template_name}_{current_date}.csv"
    csv_path = OUTPUT_DIR / csv_filename

    # Extract all possible fieldnames dynamically
    fieldnames = set()
    for row in results:
        invoice_data = json.loads(row[1])
        fieldnames.update(invoice_data.keys())  # Collect all unique keys

    fieldnames = sorted(fieldnames)  # Sort for consistency

    # Write CSV file
    with open(csv_path, "w", newline="") as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=["filename"] + fieldnames)
        csv_writer.writeheader()
        
        for row in results:
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
        # Define file paths
        pdf_path = UPLOAD_DIR / filename
        json_path = OUTPUT_DIR / f"{Path(filename).stem}.json"
        csv_path = OUTPUT_DIR / f"{Path(filename).stem}.csv"

        # Remove PDF if exists
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

