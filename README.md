# AI Clone

A self-hosted, forkable AI chatbot that represents **you** to recruiters, collaborators, or anyone who visits your link.

Fork the repo → add your data → deploy → share the URL. Visitors chat with your clone. You control everything. You pay for your own inference. No platform, no shared infrastructure.

---

## What it does

- **Public chat page** — visitors ask questions, your clone answers in your voice, grounded in your uploaded data
- **Admin dashboard** — password-protected page where you upload and manage your knowledge files (PDF, TXT, MD), trigger re-indexing, and view your current config
- **RAG pipeline** — files are chunked, embedded via Gemini, stored in ChromaDB, and retrieved at query time so answers are accurate and grounded
- **Streaming replies** — responses stream token-by-token in real time
- **Single-tenant** — one deployment = one person's clone. Your API key lives in your `.env`, never in a shared database

---

## Stack

| Concern | Choice |
|---|---|
| Backend | FastAPI + Jinja2 |
| Frontend | Server-rendered HTML + vanilla JS (no build step) |
| Vector store | ChromaDB (local, persistent) |
| LLM + embeddings | Google Gemini (`gemini-2.5-flash` + `gemini-embedding-001`) via `google-genai` |
| File parsing | `pypdf` for PDFs, plain read for TXT/MD |
| File storage | Local disk (`data/`) |
| Deployment | Fly.io (free tier with persistent disk) or Render |

**Dependencies:** `fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `google-genai`, `chromadb`, `pypdf`, `python-dotenv`, `requests`

---

## Run locally

**1. Clone and install**

```bash
git clone https://github.com/your-username/ai-clone.git
cd ai-clone
uv sync
```

**2. Configure**

```bash
cp .env.example .env
```

Edit `.env`:

```env
GEMINI_API_KEY=AIzaSy...        # from https://aistudio.google.com/app/apikey
APP_NAME=Your Name              # shown in the chat header
SYSTEM_PROMPT=You are ...       # optional voice/tone instructions
ADMIN_PASSWORD=changeme         # protects /admin
```

**3. Start**

```bash
uv run uvicorn app.main:app --reload
```

| URL | What |
|---|---|
| `http://localhost:8000` | Public chat page |
| `http://localhost:8000/admin` | Admin dashboard (requires password) |
| `http://localhost:8000/health` | Health check |

**4. Upload your data**

Go to `/admin`, enter your password, upload your files (PDF, TXT, or MD — up to 10 files, 5 MB each), click **Upload & re-index**. Once indexed, the chat page is live.

---

## Project layout

```
ai-clone/
├── app/
│   ├── main.py              Routes: /, /api/chat, /admin, /admin/ingest, /admin/delete
│   ├── ingest.py            Parse → chunk → embed → store in ChromaDB
│   ├── rag.py               Retrieve top-k chunks → build system prompt
│   ├── providers/
│   │   ├── base.py          Provider protocol (embed, embed_query, chat_stream)
│   │   └── gemini.py        Gemini impl — embeddings via REST, chat via SDK
│   └── templates/
│       ├── base.html        Shared styles
│       ├── chat.html        Public chat UI (WhatsApp-style bubbles, streaming)
│       └── admin.html       Admin dashboard (file upload, re-index, config view)
├── data/                    Knowledge files uploaded via admin (gitignored)
├── chroma/                  ChromaDB vector index (gitignored)
├── check_api.py             Diagnostic: lists available Gemini models for your key
├── fly.toml                 Fly.io deployment config (free persistent disk)
├── render.yaml              Render deployment config
├── .env.example             Environment variable template
└── pyproject.toml
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `APP_NAME` | Yes | Your name — shown in the chat header and avatar |
| `SYSTEM_PROMPT` | No | Persona and tone instructions for the model |
| `ADMIN_PASSWORD` | Yes | Password for the `/admin` dashboard |
| `DATA_DIR` | No | Where to store uploaded files (default: `data/`) |
| `CHROMA_DIR` | No | Where to store the vector index (default: `chroma/`) |

---

## Deploy to Fly.io (free, persistent disk)

```bash
brew install flyctl
fly auth signup
fly launch          # detects Python, uses fly.toml
fly volumes create ai_clone_data --size 1 --region ord
fly secrets set \
  GEMINI_API_KEY=AIzaSy... \
  APP_NAME="Your Name" \
  ADMIN_PASSWORD=your-password \
  SYSTEM_PROMPT="Your persona instructions"
fly deploy
```

Your clone is live at `https://your-app-name.fly.dev`.

After deploying, go to `https://your-app-name.fly.dev/admin` to upload your knowledge files.

---

## Deploy to Render

1. Push repo to GitHub
2. New Web Service → connect repo → Render auto-detects `render.yaml`
3. Set env vars in the Render dashboard: `GEMINI_API_KEY`, `APP_NAME`, `ADMIN_PASSWORD`, `SYSTEM_PROMPT`
4. Deploy

> **Note:** Persistent disk requires Render's Starter plan ($7/month). On the free tier, uploaded files and the vector index reset on each redeploy.

---

## RAG pipeline

```
Upload (PDF/TXT/MD)
  → Parse text (pypdf / read_text)
  → Chunk (~800 chars, 100 char overlap, paragraph-first splitting)
  → Embed (gemini-embedding-001 via REST, batches of 20 with retry on 429)
  → Store in ChromaDB collection "clone_main"

Query
  → Embed query (RETRIEVAL_QUERY task type)
  → Retrieve top-3 chunks (distance-filtered at 1.0)
  → Build system prompt (SYSTEM_PROMPT + context)
  → Stream response (gemini-2.5-flash, thinking_budget=1024)
```

---

## Adding a new LLM provider

1. Create `app/providers/<name>.py` implementing the `Provider` protocol from `base.py`:
   - `embed(texts: list[str]) -> list[list[float]]`
   - `embed_query(text: str) -> list[float]`
   - `chat_stream(system: str, history: list[dict], user: str) -> Iterator[str]`
2. Import and use it in `main.py` in place of `GeminiProvider`

---

## Diagnostic

If you get embedding errors, run this to see which models are available for your API key:

```bash
uv run python check_api.py AIzaSy...your_key_here
```

---

## Knowledge file tips

- **Plain text beats PDFs** — PDF extraction can be noisy (headers, footers, broken lines). A well-written `.md` or `.txt` file gives the model cleaner context and better answers.
- **Structure helps retrieval** — use headings and short paragraphs. Dense walls of text chunk poorly.
- **FAQ format works well** — writing Q&A pairs in your knowledge file directly improves answer quality for common questions.
- You can upload multiple files — they are all indexed together into a single collection.
