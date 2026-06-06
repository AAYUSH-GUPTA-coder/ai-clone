from app.ingest import _chroma, collection_name
from app.providers.gemini import GeminiProvider

TOP_K = 5

SYSTEM_TEMPLATE = """You are {name}'s AI clone. Answer in their voice, grounded ONLY in the context below. If the context does not contain the answer, say you don't know.

{extra}

Context:
{context}
""".strip()


def retrieve(slug: str, query: str, api_key: str) -> list[str]:
    provider = GeminiProvider(api_key)
    qvec = provider.embed_query(query)
    coll = _chroma().get_collection(collection_name(slug))
    res = coll.query(query_embeddings=[qvec], n_results=TOP_K)
    docs = res.get("documents") or [[]]
    return docs[0]


def build_system_prompt(name: str, extra: str, context_chunks: list[str]) -> str:
    context = "\n\n---\n\n".join(context_chunks) if context_chunks else "(no context found)"
    return SYSTEM_TEMPLATE.format(name=name, extra=extra or "", context=context)
