"""Embedding client for local Ollama (default model nomic-embed-text). Bounded timeout, batching and a circuit breaker so a stopped
Ollama never slows the app: callers catch EmbeddingUnavailable and fall back to keyword retrieval."""
import time
import httpx
from backend.config import settings


class EmbeddingUnavailable(Exception): ...


_cb = {"until": 0.0, "error": ""}


def enabled() -> bool: return settings.EMBED_PROVIDER == "ollama"
def last_error() -> str: return _cb["error"]


def _prefix(kind: str) -> str:
    if "nomic" in settings.EMBED_MODEL: return "search_query: " if kind == "query" else "search_document: "
    return ""


def embed(texts: list[str], kind: str = "document") -> list[list[float]]:
    if not enabled(): raise EmbeddingUnavailable("EMBED_PROVIDER is not 'ollama'")
    if time.time() < _cb["until"]: raise EmbeddingUnavailable(f"embedding service failed recently ({_cb['error']}); retrying shortly")
    out = []
    try:
        for i in range(0, len(texts), 16):
            batch = [_prefix(kind) + t[:2000] for t in texts[i:i + 16]]
            r = httpx.post(f"{settings.OLLAMA_URL}/api/embed", json={"model": settings.EMBED_MODEL, "input": batch}, timeout=settings.EMBED_TIMEOUT_S)
            if r.status_code == 404:  # older Ollama: one text per call
                for t in batch:
                    r2 = httpx.post(f"{settings.OLLAMA_URL}/api/embeddings", json={"model": settings.EMBED_MODEL, "prompt": t}, timeout=settings.EMBED_TIMEOUT_S)
                    r2.raise_for_status(); out.append(r2.json()["embedding"])
                continue
            r.raise_for_status(); out.extend(r.json()["embeddings"])
    except (httpx.HTTPError, KeyError, ValueError) as e:
        _cb["until"] = time.time() + 30; _cb["error"] = str(e)[:120]
        raise EmbeddingUnavailable(f"Ollama embeddings failed: {_cb['error']}")
    _cb["error"] = ""
    return out


def embed_query(q: str) -> list[float]: return embed([q], "query")[0]
