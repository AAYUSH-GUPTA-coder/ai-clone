# AI Clone Builder

A weekend-scale, BYO-key multi-tenant chatbot builder. Anyone can paste their Gemini key, upload PDF/TXT/MD files, and get a shareable chat URL. Visitors chat with the clone using the *owner's* API key — you (the host) pay nothing for inference.

## Stack

- **Backend + Frontend:** FastAPI + Jinja2, server-rendered HTML, vanilla JS streaming
- **DB:** SQLite (`app.db`)
- **Vector store:** ChromaDB (`./chroma/`)
- **LLM:** Google Gemini via `google-genai`
- **Keys at rest:** Fernet-encrypted with `APP_SECRET`

## Run locally

```bash
uv sync
cp .env.example .env
# Edit .env and set APP_SECRET:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

uv run uvicorn app.main:app --reload
```

Open <http://localhost:8000>, paste a Gemini key (<https://aistudio.google.com/app/apikey>), upload files, get a share URL.

## Layout

```
app/
  main.py           routes
  db.py             sqlite schema + helpers
  crypto.py         Fernet wrap/unwrap
  ingest.py         parse + chunk + embed + store
  rag.py            retrieve + prompt build
  providers/
    base.py         Provider protocol
    gemini.py       google-genai impl
  templates/        create / created / chat / base
data/               user uploads (gitignored)
chroma/             vector index (gitignored)
app.db              sqlite (gitignored)
```

## Adding a new provider

Implement `embed`, `embed_query`, `chat_stream` in `app/providers/<name>.py`, then route on the `provider` column in `main.py`. The protocol lives in `providers/base.py`.

## Security

- Keys are Fernet-encrypted before insert into SQLite.
- `APP_SECRET` must be a 32-byte url-safe base64 key — see `.env.example`.
- File uploads capped: 10 files × 5 MB, `.pdf` / `.txt` / `.md` only.
- The owner gets a one-time **edit URL** — there is no login.

## Status

MVP scaffold complete. See `/Users/aayush/.claude/plans/i-am-creating-the-whimsical-hollerith.md` for the full plan, including nice-to-haves (rate limiting, edit page, multi-provider).
