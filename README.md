# AI Clone - Your Personal AI Representative

> **"What do you work on?" "Are you open to new roles?" "What's your tech stack?"**
> Recruiters ask the same questions. Your clone answers them - instantly, accurately, 24/7.

**[Chat with the live clone →](https://aayush-ai-clone.fly.dev/)**

---

## What is an AI Clone?

An AI Clone is a chatbot that represents **you**. It knows your background, your projects, your skills, and your story - and it answers questions about you the way you would answer them yourself.

You give it your resume, LinkedIn profile, or a simple text file about yourself. It learns from that. Visitors can then have a real conversation with your clone - asking anything from *"What projects have you built?"* to *"Why should I hire you?"* - and get accurate, thoughtful answers in your voice.

No hallucinations. No generic responses. Every answer is grounded in what you've actually shared about yourself.

---

## Why you need one

**For job seekers and professionals:**
- Recruiters reach out at all hours. Your clone is always available.
- Share a single link instead of a resume - far more memorable.
- Let your personality and depth come through in a conversation, not a PDF.
- Filter serious interest: someone who chats with your clone is more engaged than someone who skimmed your LinkedIn.

**For developers:**
- Fork the repo, fill in a `.env` file, deploy in under 10 minutes.
- Clean, minimal codebase - FastAPI + ChromaDB + Gemini. No magic, no abstractions you can't understand.
- Extend it: swap the LLM provider, add auth, connect a calendar - it's your code.

---

## Try it live

Chat with Aayush Gupta's AI clone right now:

**[https://aayush-ai-clone.fly.dev/](https://aayush-ai-clone.fly.dev/)**

Try asking:
- *"What are you currently working on?"*
- *"What's your experience with AI?"*
- *"Have you won any hackathons?"*
- *"Are you open to new opportunities?"*
- *"How can I reach you?"*

---

## Create your own clone in 10 minutes

You don't need to be a developer to have a clone. If you can edit a text file and run two commands, you can deploy one.

**Step 1 - Fork this repo**

Click **Fork** in the top right on GitHub. You now have your own copy.

**Step 2 - Write your knowledge file**

Create a file called `me.md` (plain text works great). Write about yourself:

```
# About Me
My name is [Your Name]. I'm a [your role] based in [city].

# What I'm working on
Currently building [project] at [company]...

# My skills
[list them out]

# What I'm looking for
[be honest about this]
```

The more detail you add, the better your clone answers. FAQ format works especially well - write the questions recruiters actually ask, then answer them.

**Step 3 - Configure**

```bash
cp .env.example .env
```

Edit `.env`:

```env
GEMINI_API_KEY=AIzaSy...        # free at https://aistudio.google.com/app/apikey
APP_NAME=Your Name
SYSTEM_PROMPT=You are [Your Name]'s AI clone. Speak in first person, be concise and direct.
ADMIN_PASSWORD=choose-a-password
```

That's it. Four lines.

**Step 4 - Deploy to Fly.io**

```bash
brew install flyctl
fly auth signup
fly apps create your-name-ai-clone
fly volumes create ai_clone_data --size 1 --region ord --app your-name-ai-clone
fly secrets set \
  GEMINI_API_KEY="your-key" \
  APP_NAME="Your Name" \
  ADMIN_PASSWORD="your-password" \
  SYSTEM_PROMPT="your persona instructions" \
  --app your-name-ai-clone
fly deploy
```

Your clone is live at `https://your-name-ai-clone.fly.dev`.

**Step 5 - Upload your knowledge file**

Go to `https://your-app.fly.dev/admin`, log in with your password, upload your `.md` or `.txt` file, and click **Upload & re-index**. Done.

Share the link. Anyone who visits can chat with your clone.

---

## Run locally

```bash
git clone https://github.com/your-username/ai-clone.git
cd ai-clone
uv sync
cp .env.example .env   # fill in your values
uv run uvicorn app.main:app --reload
```

| URL | What |
|---|---|
| `http://localhost:8000` | Public chat page |
| `http://localhost:8000/admin` | Admin dashboard (requires password) |
| `http://localhost:8000/health` | Health check |

---

## How it works

```
Your file (PDF / TXT / MD)
  → split into chunks
  → each chunk converted to a vector (Gemini Embedding)
  → stored in ChromaDB

Visitor asks a question
  → question converted to vector
  → find most relevant chunks from your file
  → Gemini reads those chunks and generates a grounded answer
  → streamed back token by token
```

Answers are **always grounded in your data**. The model is instructed not to use outside knowledge - it won't make things up about you.

---

## Stack

| Concern | Choice |
|---|---|
| Backend | FastAPI + Jinja2 |
| Frontend | Server-rendered HTML + vanilla JS (no build step) |
| Vector store | ChromaDB (local, persistent) |
| LLM | `gemini-2.5-flash` with `thinking_budget=1024` for accuracy |
| Embeddings | `gemini-embedding-001` via REST |
| File parsing | `pypdf` for PDFs, plain read for TXT/MD |
| Deployment | Fly.io (persistent volume) or Render |

---

## Project layout

```
ai-clone/
├── app/
│   ├── main.py              Routes: /, /api/chat, /admin, /admin/ingest, /admin/delete
│   ├── ingest.py            Parse → chunk → embed → store in ChromaDB
│   ├── rag.py               Retrieve top-k chunks → build system prompt
│   ├── providers/
│   │   ├── base.py          Provider protocol
│   │   └── gemini.py        Gemini - embeddings via REST, chat via SDK
│   └── templates/
│       ├── chat.html        Public chat UI (WhatsApp-style, streaming)
│       └── admin.html       Admin dashboard (upload, re-index, config)
├── data/                    Your knowledge files (gitignored)
├── chroma/                  Vector index (gitignored)
├── Dockerfile               For Fly.io deployment
├── fly.toml                 Fly.io config
├── .env.example             Environment variable template
└── pyproject.toml
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Free at [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `APP_NAME` | Yes | Your name - shown in the chat header and avatar |
| `SYSTEM_PROMPT` | No | Persona and tone instructions for the model |
| `ADMIN_PASSWORD` | Yes | Password for the `/admin` dashboard |
| `DATA_DIR` | No | File storage path (default: `data/`) |
| `CHROMA_DIR` | No | Vector index path (default: `chroma/`) |

---

## Knowledge file tips

- **Plain text beats PDFs** - PDF extraction can be noisy. A well-written `.md` or `.txt` file gives the model cleaner context and better answers.
- **FAQ format works best** - write the questions recruiters actually ask, then answer them directly. The model retrieves those Q&A pairs at query time.
- **Be specific** - dates, company names, project details, numbers. Vague input produces vague output.
- **Write in first person** - *"I built..."*, *"I'm looking for..."*. The clone speaks in your voice.
- **Multiple files are fine** - they're all indexed together into one collection.

---

## Adding a new LLM provider

The provider interface is simple:

```python
def embed(texts: list[str]) -> list[list[float]]: ...
def embed_query(text: str) -> list[float]: ...
def chat_stream(system: str, history: list[dict], user: str) -> Iterator[str]: ...
```

Create `app/providers/openai.py` (or any provider), implement those three methods, swap it in `main.py`. The rest of the app doesn't change.

---

## Diagnostic

If you get embedding errors, run this to see which Gemini models are available for your API key:

```bash
uv run python check_api.py AIzaSy...your_key_here
```
