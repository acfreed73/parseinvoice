from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from server.app.routers import files, processing, templates, downloads  # ✅ Import routers

app = FastAPI()

# ✅ Mount Static Files
app.mount("/static", StaticFiles(directory="server/static"), name="static")

# ✅ Include Routers with Correct Prefixes
app.include_router(files.router, prefix="/files", tags=["Files"])
app.include_router(processing.router, prefix="/processing", tags=["Processing"])
app.include_router(templates.router, prefix="/templates", tags=["Templates"])
app.include_router(downloads.router, prefix="/downloads", tags=["Downloads"])  # ✅ Fix downloads prefix

# ✅ Setup Jinja2 Templates
templates = Jinja2Templates(directory="server/templates")

@app.get("/")
async def home(request: Request):
    """Serves the main frontend template."""
    return templates.TemplateResponse("index.html", {"request": request})
