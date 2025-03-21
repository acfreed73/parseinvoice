from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path
import mistune  # Ensure mistune is installed: pip install mistune
from server.app.routers import files, processing, templates, downloads, templates_api

app = FastAPI()

DOCS_PATH = Path("server/docs/template_docs.md")

# ✅ Mount Static Files (CSS, JS, images, etc.)
app.mount("/static", StaticFiles(directory="server/static"), name="static")

# ✅ Include Routers with Correct Prefixes
app.include_router(files.router, prefix="/files", tags=["Files"])
app.include_router(processing.router, prefix="/processing", tags=["Processing"])
app.include_router(templates.router, prefix="/templates", tags=["Templates"])
app.include_router(downloads.router, prefix="/downloads", tags=["Downloads"])
app.include_router(templates_api.router, prefix="/templates", tags=["Templates"])

# ✅ Setup Jinja2 Templates
templates = Jinja2Templates(directory="server/templates")

def get_all_files():
    unprocessed_dir = Path("data/unprocessed")
    processed_dir = Path("data/pdfs")

    files = []

    for path in unprocessed_dir.glob("*.pdf"):
        files.append({
            "filename": path.name,
            "unprocessed": True
        })

    for path in processed_dir.glob("*.pdf"):
        files.append({
            "filename": path.name,
            "unprocessed": False
        })
    return files
@app.get("/")
async def home(request: Request):
    files = get_all_files()  # whatever you're currently using to list files
    print(f"files: {files}")
    raw_template_files = list(Path("data/templates_raw").glob("*.yml"))
    raw_templates = [t.name for t in raw_template_files]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "files": files,
        "raw_templates": raw_templates  # ✅ required for dropdown to populate
    })

@app.get("/docs/help/", response_class=HTMLResponse)
async def serve_markdown():
    """Convert Markdown to HTML and serve it as a webpage."""
    if not DOCS_PATH.exists():
        return HTMLResponse("<h1>Documentation not found</h1>", status_code=404)

    with open(DOCS_PATH, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    html_content = mistune.markdown(md_content)

    return HTMLResponse(f"""
    <html>
    <head>
        <title>Template Documentation</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                max-width: 800px;
                line-height: 1.6;
            }}
            h1, h2, h3 {{
                color: #333;
            }}
            pre {{
                background: #f4f4f4;
                padding: 10px;
                border-radius: 5px;
                overflow-x: auto;
            }}
            code {{
                font-family: monospace;
                background: #eef;
                padding: 3px;
                border-radius: 4px;
            }}
        </style>
    </head>
    <body>
        <h1>Template Documentation</h1>
        {html_content}
    </body>
    </html>
    """)
