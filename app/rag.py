from app.ingest import COLLECTION_NAME, _chroma
from app.providers.gemini import GeminiProvider

TOP_K = 3           # fewer chunks = tighter, more focused context
MAX_DISTANCE = 1.0  # discard chunks too far from the query (0=identical, 2=opposite)

SYSTEM_TEMPLATE = """{extra}

Answer based ONLY on the context below. Do not use outside knowledge.

Context:
{context}
""".strip()


def retrieve(query: str, api_key: str) -> list[str]:
    provider = GeminiProvider(api_key)
    qvec = provider.embed_query(query)
    coll = _chroma().get_collection(COLLECTION_NAME)
    res = coll.query(query_embeddings=[qvec], n_results=TOP_K, include=["documents", "distances"])
    docs      = (res.get("documents") or [[]])[0]
    distances = (res.get("distances") or [[]])[0]
    # Filter out weakly related chunks
    return [doc for doc, dist in zip(docs, distances) if dist <= MAX_DISTANCE]


def build_system_prompt(name: str, extra: str, context_chunks: list[str]) -> str:
    context = "\n\n---\n\n".join(context_chunks) if context_chunks else "(no relevant context found)"
    return SYSTEM_TEMPLATE.format(extra=extra or "", context=context)
