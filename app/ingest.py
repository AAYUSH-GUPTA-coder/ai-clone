from pathlib import Path

import chromadb
from pypdf import PdfReader

from app.providers.gemini import GeminiProvider

CHROMA_DIR = Path("chroma")
DATA_DIR = Path("data")

MAX_CHARS = 800
OVERLAP = 100


def _chroma() -> chromadb.api.ClientAPI:
    CHROMA_DIR.mkdir(exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def collection_name(slug: str) -> str:
    return f"clone_{slug.replace('-', '_')}"


def parse_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if ext in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"Unsupported file type: {ext}")


def chunk_text(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + MAX_CHARS, n)
        if end < n:
            # try to break on a paragraph or sentence boundary
            for sep in ("\n\n", "\n", ". ", " "):
                cut = text.rfind(sep, i + MAX_CHARS // 2, end)
                if cut != -1:
                    end = cut + len(sep)
                    break
        chunks.append(text[i:end].strip())
        if end >= n:
            break
        i = max(end - OVERLAP, i + 1)
    return [c for c in chunks if c]


def ingest_clone(slug: str, files: list[Path], api_key: str) -> int:
    """Parse, chunk, embed, store. Returns chunk count."""
    all_chunks: list[str] = []
    all_metas: list[dict] = []
    for path in files:
        text = parse_file(path)
        for chunk in chunk_text(text):
            all_chunks.append(chunk)
            all_metas.append({"source": path.name})

    if not all_chunks:
        return 0

    provider = GeminiProvider(api_key)
    vectors = provider.embed(all_chunks)

    client = _chroma()
    name = collection_name(slug)
    # fresh collection on each ingest so re-uploads replace old content
    try:
        client.delete_collection(name)
    except Exception:
        pass
    coll = client.create_collection(name=name)
    coll.add(
        ids=[f"{slug}-{i}" for i in range(len(all_chunks))],
        documents=all_chunks,
        embeddings=vectors,
        metadatas=all_metas,
    )
    return len(all_chunks)
