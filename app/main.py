import json
import logging
import os
import secrets
import traceback
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from app.ingest import DATA_DIR, ingest, list_files
from app.providers.gemini import GeminiProvider
from app.rag import build_system_prompt, retrieve

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

ALLOWED_EXTS = {".pdf", ".txt", ".md"}
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_FILES = 10

app = FastAPI(title="AI Clone")
security = HTTPBasic()
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(500, "GEMINI_API_KEY not set.")
    return key


def _clone_name() -> str:
    return os.environ.get("APP_NAME", "AI Clone")


def _system_prompt() -> str:
    return os.environ.get("SYSTEM_PROMPT", "")


def _require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not password:
        raise HTTPException(500, "ADMIN_PASSWORD not set.")
    ok = secrets.compare_digest(credentials.password.encode(), password.encode())
    if not ok:
        raise HTTPException(
            status_code=401,
            detail="Wrong password.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.on_event("startup")
def _startup() -> None:
    DATA_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def chat_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "chat.html",
        {"name": _clone_name()},
    )


@app.post("/api/chat")
async def chat_api(request: Request) -> StreamingResponse:
    payload = await request.json()
    message = (payload.get("message") or "").strip()
    history = payload.get("history") or []
    if not message:
        raise HTTPException(400, "Empty message.")

    api_key = _api_key()

    try:
        context = retrieve(message, api_key)
    except Exception:
        # Collection may not exist yet (no files ingested)
        context = []

    system = build_system_prompt(_clone_name(), _system_prompt(), context)
    provider = GeminiProvider(api_key)

    def event_stream() -> Iterator[bytes]:
        try:
            for token in provider.chat_stream(system, history, message):
                yield f"data: {json.dumps({'token': token})}\n\n".encode()
        except Exception as e:
            log.error("chat_stream error: %s", traceback.format_exc())
            yield f"data: {json.dumps({'error': str(e)})}\n\n".encode()
        yield b"data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, _: str = Depends(_require_admin)) -> HTMLResponse:
    files = list_files()
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "name": _clone_name(),
            "system_prompt": _system_prompt(),
            "files": [f.name for f in files],
            "saved": False,
        },
    )


@app.post("/admin/reindex", response_class=HTMLResponse)
async def admin_reindex(
    request: Request,
    _: str = Depends(_require_admin),
) -> HTMLResponse:
    """Re-index all existing files without uploading new ones."""
    existing = list_files()
    if not existing:
        raise HTTPException(400, "No files to index. Upload some files first.")
    try:
        chunk_count = ingest(existing, _api_key())
    except Exception as e:
        log.error("Re-index error:\n%s", traceback.format_exc())
        raise HTTPException(400, f"Indexing failed: {e}") from e

    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "name": _clone_name(),
            "system_prompt": _system_prompt(),
            "files": [f.name for f in list_files()],
            "saved": True,
            "chunks": chunk_count,
        },
    )


@app.post("/admin/ingest", response_class=HTMLResponse)
async def admin_ingest(
    request: Request,
    uploads: list[UploadFile] = File(default=[]),
    _: str = Depends(_require_admin),
) -> HTMLResponse:
    uploads = [f for f in uploads if f.filename]
    if not uploads:
        raise HTTPException(400, "Select at least one file.")
    if len(uploads) > MAX_FILES:
        raise HTTPException(400, f"At most {MAX_FILES} files at a time.")

    DATA_DIR.mkdir(exist_ok=True)
    saved: list[Path] = []
    for upload in uploads:
        ext = Path(upload.filename).suffix.lower()
        if ext not in ALLOWED_EXTS:
            raise HTTPException(400, f"Unsupported: {upload.filename}")
        body = await upload.read()
        if len(body) > MAX_FILE_BYTES:
            raise HTTPException(400, f"{upload.filename} exceeds 5 MB.")
        dest = DATA_DIR / Path(upload.filename).name
        dest.write_bytes(body)
        saved.append(dest)

    try:
        all_files = list_files()
        chunk_count = ingest(all_files, _api_key())
    except Exception as e:
        log.error("Ingest error:\n%s", traceback.format_exc())
        raise HTTPException(400, f"Ingestion failed: {e}") from e

    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "name": _clone_name(),
            "system_prompt": _system_prompt(),
            "files": [f.name for f in list_files()],
            "saved": True,
            "chunks": chunk_count,
        },
    )


@app.post("/admin/delete", response_class=HTMLResponse)
async def admin_delete(
    request: Request,
    filename: str = Form(...),
    _: str = Depends(_require_admin),
) -> HTMLResponse:
    try:
        # Use resolve() so relative vs absolute paths compare correctly
        target = (DATA_DIR / Path(filename).name).resolve()
        data_dir_resolved = DATA_DIR.resolve()
        if target.parent != data_dir_resolved:
            raise HTTPException(400, "Invalid filename.")
        if target.exists():
            target.unlink()
            log.info("Deleted file: %s", filename)
    except HTTPException:
        raise
    except Exception:
        log.error("Delete failed:\n%s", traceback.format_exc())
        raise HTTPException(500, "Could not delete file.")

    remaining = list_files()
    if remaining:
        try:
            ingest(remaining, _api_key())
        except Exception:
            log.error("Re-ingest after delete failed:\n%s", traceback.format_exc())

    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "name": _clone_name(),
            "system_prompt": _system_prompt(),
            "files": [f.name for f in remaining],
            "saved": False,
            "deleted": filename,
        },
    )
