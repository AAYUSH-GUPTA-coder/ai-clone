import time
from typing import Iterator

import requests
from google import genai
from google.genai import types

EMBED_MODEL = "gemini-embedding-001"
CHAT_MODEL = "gemini-2.5-flash"
EMBED_BATCH = 20          # small batches to stay inside 30K TPM free limit
GEMINI_REST = "https://generativelanguage.googleapis.com/v1beta"
_MAX_RETRIES = 4
_RETRY_DELAY = 15         # seconds to wait on first 429; doubles each retry


class GeminiProvider:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = genai.Client(api_key=api_key)

    # --- embeddings via direct REST (avoids SDK routing issues) ---

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH):
            batch = texts[i : i + EMBED_BATCH]
            out.extend(self._batch_embed_rest(batch, "RETRIEVAL_DOCUMENT"))
            if i + EMBED_BATCH < len(texts):
                time.sleep(1)   # brief pause between batches
        return out

    def embed_query(self, text: str) -> list[float]:
        return self._batch_embed_rest([text], "RETRIEVAL_QUERY")[0]

    def _batch_embed_rest(self, texts: list[str], task_type: str) -> list[list[float]]:
        url = f"{GEMINI_REST}/models/{EMBED_MODEL}:batchEmbedContents"
        payload = {
            "requests": [
                {
                    "model": f"models/{EMBED_MODEL}",
                    "content": {"parts": [{"text": t}]},
                    "taskType": task_type,
                }
                for t in texts
            ]
        }
        delay = _RETRY_DELAY
        for attempt in range(_MAX_RETRIES):
            resp = requests.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self._api_key},
                timeout=60,
            )
            if resp.status_code == 429:
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
            resp.raise_for_status()
            return [e["values"] for e in resp.json()["embeddings"]]
        resp.raise_for_status()  # final attempt exhausted

    # --- chat via SDK (streaming is easier through it) ---

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
