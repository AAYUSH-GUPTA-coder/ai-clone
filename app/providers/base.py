from typing import Iterator, Protocol


class Provider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def chat_stream(self, system: str, history: list[dict], user: str) -> Iterator[str]: ...
