import json
import os
import secrets
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from nanoid import generate as nanoid
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import crypto, db
from app.ingest import DATA_DIR, ingest_clone
from app.providers.gemini import GeminiProvider
from app.rag import build_system_prompt, retrieve

load_dotenv()

ALLOWED_EXTS = {".pdf", ".txt", ".md"}
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_FILES = 10

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="AI Clone Builder")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def _startup() -> None:
    db.init()
    DATA_DIR.mkdir(exist_ok=True)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def create_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "create.html")


@app.post("/", response_class=HTMLResponse)
async def create_clone(
    request: Request,
    name: str = Form(...),
    provider: str = Form("gemini"),
    api_key: str = Form(...),
    system_prompt: str = Form(""),
    files: list[UploadFile] = File(...),
) -> HTMLResponse:
    if provider != "gemini":
        raise HTTPException(400, "Only Gemini is supported right now.")

    files = [f for f in files if f.filename]
    if not files:
        raise HTTPException(400, "Upload at least one file.")
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"At most {MAX_FILES} files.")

    slug = "c-" + nanoid(size=8).lower()
    edit_secret = secrets.token_urlsafe(24)
    clone_dir = DATA_DIR / slug
    clone_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []
    for upload in files:
        ext = Path(upload.filename).suffix.lower()
        if ext not in ALLOWED_EXTS:
            raise HTTPException(400, f"Unsupported file: {upload.filename}")
        body = await upload.read()
        if len(body) > MAX_FILE_BYTES:
            raise HTTPException(400, f"{upload.filename} exceeds 5MB.")
        dest = clone_dir / Path(upload.filename).name
        dest.write_bytes(body)
        saved_paths.append(dest)

    try:
        chunk_count = ingest_clone(slug, saved_paths, api_key)
    except Exception as e:
        # ingest failed (bad key, parse error, etc.) — clean up and report
        for p in saved_paths:
            p.unlink(missing_ok=True)
        clone_dir.rmdir()
        raise HTTPException(400, f"Ingestion failed: {e}") from e

    if chunk_count == 0:
        raise HTTPException(400, "No text could be extracted from the uploaded files.")

    db.insert_clone(
        slug=slug,
        edit_secret=edit_secret,
        name=name.strip() or "Clone",
        provider=provider,
        api_key_encrypted=crypto.encrypt(api_key),
        system_prompt=system_prompt.strip(),
    )

    base = os.environ.get("BASE_URL", str(request.base_url).rstrip("/"))
    return templates.TemplateResponse(
        request,
        "created.html",
        {
            "name": name,
            "share_url": f"{base}/c/{slug}",
            "edit_url": f"{base}/edit/{slug}/{edit_secret}",
            "chunks": chunk_count,
        },
    )


@app.get("/c/{slug}", response_class=HTMLResponse)
def chat_page(request: Request, slug: str) -> HTMLResponse:
    row = db.get_clone(slug)
    if not row:
        raise HTTPException(404, "Clone not found.")
    return templates.TemplateResponse(
        request,
        "chat.html",
        {"slug": slug, "name": row["name"]},
    )


@app.get("/edit/{slug}/{secret}", response_class=HTMLResponse)
def edit_page(request: Request, slug: str, secret: str) -> HTMLResponse:
    row = db.get_clone(slug)
    if not row or row["edit_secret"] != secret:
        raise HTTPException(404, "Not found or wrong secret.")
    return templates.TemplateResponse(
        request,
        "edit.html",
        {"slug": slug, "secret": secret, "name": row["name"], "system_prompt": row["system_prompt"]},
    )


@app.post("/edit/{slug}/{secret}", response_class=HTMLResponse)
async def edit_clone(
    request: Request,
    slug: str,
    secret: str,
    name: str = Form(...),
    system_prompt: str = Form(""),
    new_api_key: str = Form(""),
    files: list[UploadFile] = File(default=[]),
) -> HTMLResponse:
    row = db.get_clone(slug)
    if not row or row["edit_secret"] != secret:
        raise HTTPException(404, "Not found or wrong secret.")

    # re-ingest if new files uploaded
    uploaded = [f for f in files if f.filename]
    if uploaded:
        if len(uploaded) > MAX_FILES:
            raise HTTPException(400, f"At most {MAX_FILES} files.")
        clone_dir = DATA_DIR / slug
        clone_dir.mkdir(parents=True, exist_ok=True)
        # remove old uploads
        for old in clone_dir.iterdir():
            old.unlink()
        saved_paths: list[Path] = []
        for upload in uploaded:
            ext = Path(upload.filename).suffix.lower()
            if ext not in ALLOWED_EXTS:
                raise HTTPException(400, f"Unsupported file: {upload.filename}")
            body = await upload.read()
            if len(body) > MAX_FILE_BYTES:
                raise HTTPException(400, f"{upload.filename} exceeds 5MB.")
            dest = clone_dir / Path(upload.filename).name
            dest.write_bytes(body)
            saved_paths.append(dest)
        key_for_ingest = (new_api_key.strip() or crypto.decrypt(row["api_key_encrypted"]))
        try:
            ingest_clone(slug, saved_paths, key_for_ingest)
        except Exception as e:
            raise HTTPException(400, f"Ingestion failed: {e}") from e

    encrypted = crypto.encrypt(new_api_key.strip()) if new_api_key.strip() else None
    db.update_clone(
        slug=slug,
        name=name.strip() or row["name"],
        system_prompt=system_prompt.strip(),
        api_key_encrypted=encrypted,
    )

    base = os.environ.get("BASE_URL", str(request.base_url).rstrip("/"))
    return templates.TemplateResponse(
        request,
        "edit.html",
        {
            "slug": slug,
            "secret": secret,
            "name": name.strip() or row["name"],
            "system_prompt": system_prompt.strip(),
            "saved": True,
            "share_url": f"{base}/c/{slug}",
        },
    )


@app.post("/api/chat/{slug}")
@limiter.limit("30/minute")
async def chat_api(slug: str, request: Request) -> StreamingResponse:
    row = db.get_clone(slug)
    if not row:
        raise HTTPException(404, "Clone not found.")

    payload = await request.json()
    message = (payload.get("message") or "").strip()
    history = payload.get("history") or []
    if not message:
        raise HTTPException(400, "Empty message.")

    api_key = crypto.decrypt(row["api_key_encrypted"])
    context = retrieve(slug, message, api_key)
    system = build_system_prompt(row["name"], row["system_prompt"], context)
    provider = GeminiProvider(api_key)

    def event_stream() -> Iterator[bytes]:
        try:
            for token in provider.chat_stream(system, history, message):
                yield f"data: {json.dumps({'token': token})}\n\n".encode()
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n".encode()
        yield b"data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
