from typing import Iterator

from google import genai
from google.genai import types

EMBED_MODEL = "text-embedding-004"
CHAT_MODEL = "gemini-2.0-flash"
EMBED_BATCH = 100


class GeminiProvider:
    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH):
            batch = texts[i : i + EMBED_BATCH]
            resp = self._client.models.embed_content(
                model=EMBED_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            )
            out.extend(e.values for e in resp.embeddings)
        return out

    def embed_query(self, text: str) -> list[float]:
        resp = self._client.models.embed_content(
            model=EMBED_MODEL,
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        return resp.embeddings[0].values

    def chat_stream(self, system: str, history: list[dict], user: str) -> Iterator[str]:
        contents = []
        for turn in history:
            contents.append(
                types.Content(role=turn["role"], parts=[types.Part(text=turn["content"])])
            )
        contents.append(types.Content(role="user", parts=[types.Part(text=user)]))

        stream = self._client.models.generate_content_stream(
            model=CHAT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text
