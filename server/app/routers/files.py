import shutil
import json
import sqlite3
import subprocess
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from server.app.utils import clean_json_output

router = APIRouter()

UPLOAD_DIR = Path("data/pdfs")
TEXT_DIR = Path("data/text")
UNPROCESSED_DIR = Path("data/unprocessed")
DB_PATH = Path("data/invoices.db")
TEMPLATE_DIR = Path("data/templates")
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

for directory in [UPLOAD_DIR, TEXT_DIR, UNPROCESSED_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

def sanitize_filename(filename):
    """Sanitize filenames by removing special characters and spaces."""
    return filename.replace(" ", "_")

def process_invoice(filename: str):
    """Processes an invoice using invoice2data and updates the database."""
    print(f"🔹 Processing invoice: {filename}")
    file_path = UPLOAD_DIR / filename

    result = subprocess.run(
        ["invoice2data", "--template-folder", str(TEMPLATE_DIR), "--output-format", "json", str(file_path)],
        capture_output=True, text=True
    )

    print("Processing Output:", result.stdout)
    print("Processing Error:", result.stderr)

    # ✅ Use shared JSON extraction
    json_data = clean_json_output(result.stderr)

    if "No template" in result.stderr or not json_data:
        unprocessed_path = UNPROCESSED_DIR / filename
        shutil.move(file_path, unprocessed_path)
        return {"message": f"Processing failed for {filename}. Moved to unprocessed folder.", "status": "failed"}

    # ✅ Store valid JSON
    try:
        json_string = json.dumps(json_data, indent=2)
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO invoices (filename, json_data) VALUES (?, ?)", (filename, json_string))
        conn.commit()
    except sqlite3.OperationalError as e:
        unprocessed_path = UNPROCESSED_DIR / filename
        shutil.move(file_path, unprocessed_path)
        return {"message": f"Database error: {e}. Moved to unprocessed folder.", "status": "failed"}
    finally:
        conn.close()

    return {"message": f"Successfully processed {filename}", "filename": filename, "status": "success"}

    # Store in database
    try:
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO invoices (filename, json_data) VALUES (?, ?)", (filename, json_string))
        conn.commit()
    except sqlite3.OperationalError as e:
        unprocessed_path = UNPROCESSED_DIR / filename
        shutil.move(file_path, unprocessed_path)
        return {"message": f"Database error: {e}. Moved back to unprocessed folder.", "status": "failed"}
    finally:
        conn.close()

    return {"message": f"Successfully processed {filename}", "filename": filename, "status": "success"}

@router.post("/upload/")
async def upload_pdf(file: UploadFile = File(...)):
    """Handles PDF file upload and automatically triggers processing."""
    file_path = UPLOAD_DIR / file.filename

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    # Process the file automatically
    return process_invoice(file.filename)

@router.get("/uploaded_files/")
async def get_uploaded_files():
    """List uploaded and processed files."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    uploaded_files = {f.name for f in UPLOAD_DIR.glob("*.pdf")}
    unprocessed_files = {f.name for f in UNPROCESSED_DIR.glob("*.pdf")}
    
    c.execute("SELECT filename FROM invoices WHERE json_data IS NOT NULL")
    processed_files = {row[0] for row in c.fetchall()}
    conn.close()

    files = []
    all_files = uploaded_files | unprocessed_files | processed_files  # Ensure all sources are checked
    
    for f in all_files:
        files.append({
            "filename": f,
            "processed": f in processed_files,
            "unprocessed": f in unprocessed_files
        })
    
    return JSONResponse(content={"files": files})

@router.delete("/delete/{filename}")
async def delete_file(filename: str):
    """Deletes a file from storage and database."""
    file_path = UPLOAD_DIR / filename
    text_file = TEXT_DIR / f"{filename}.txt"
    unprocessed_file = UNPROCESSED_DIR / filename
    
    # Remove from database
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM invoices WHERE filename = ?", (filename,))
    conn.commit()
    conn.close()
    
    # Delete files from storage
    for f in [file_path, text_file, unprocessed_file]:
        if f.exists():
            f.unlink()
    
    return {"message": f"Deleted {filename} successfully."}

@router.post("/reset/")
async def reset_system():
    """Resets the system by deleting all files and clearing the database."""
    # Delete all files
    for directory in [UPLOAD_DIR, TEXT_DIR, UNPROCESSED_DIR]:
        for file in directory.glob("*"):
            file.unlink()
    
    # Clear database
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM invoices")
    conn.commit()
    conn.close()
    
    return {"message": "System reset complete."}

@router.post("/retry/{filename}")
async def retry_processing(filename: str):
    """Retries processing of a failed invoice by moving it back to pdfs folder and reprocessing."""
    print(f"🔄 Retrying processing for: {filename}")
    unprocessed_path = UNPROCESSED_DIR / filename
    file_path = UPLOAD_DIR / filename

    if not unprocessed_path.exists():
        raise HTTPException(status_code=404, detail="File not found in unprocessed folder.")

    try:
        shutil.move(unprocessed_path, file_path)
        print(f"✅ Moved {filename} from unprocessed to pdfs.")  # Log movement
    except Exception as e:
        print(f"❌ Failed to move {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to move file: {e}")

    return process_invoice(filename)
