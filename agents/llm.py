"""LLM access with timeouts, bounded retries and cost tracking. Provider 'none' (default) or any
failure raises LLMUnavailable so callers use the deterministic fallback."""
import json, time
import httpx
from backend.config import settings


class LLMUnavailable(Exception): ...
class LLMTimeout(LLMUnavailable): ...


def complete_json(system: str, user: str, simulate_timeout: bool = False) -> tuple[dict, dict]:
    meta = {"provider": settings.LLM_PROVIDER, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "attempts": 0}
    if simulate_timeout:  # scenario s10: prove retry + fallback paths
        for i in range(settings.LLM_MAX_RETRIES + 1):
            meta["attempts"] += 1
            time.sleep(settings.RETRY_BACKOFF_S * (2 ** i))
        raise LLMTimeout(f"LLM timed out after {meta['attempts']} attempts")
    if settings.LLM_PROVIDER == "none":
        raise LLMUnavailable("no LLM provider configured (LLM_PROVIDER=none)")
    last = None
    for i in range(settings.LLM_MAX_RETRIES + 1):
        meta["attempts"] += 1
        try:
            t0 = time.time()
            if settings.LLM_PROVIDER == "anthropic":
                r = httpx.post("https://api.anthropic.com/v1/messages", timeout=settings.LLM_TIMEOUT_S,
                               headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
                               json={"model": settings.ANTHROPIC_MODEL, "max_tokens": 1000, "system": system,
                                     "messages": [{"role": "user", "content": user}]})
                r.raise_for_status(); d = r.json()
                text = "".join(b.get("text", "") for b in d["content"])
                meta["tokens_in"], meta["tokens_out"] = d["usage"]["input_tokens"], d["usage"]["output_tokens"]
            elif settings.LLM_PROVIDER == "ollama":
                r = httpx.post(f"{settings.OLLAMA_URL}/api/chat", timeout=settings.LLM_TIMEOUT_S,
                               json={"model": settings.OLLAMA_MODEL, "stream": False, "format": "json",
                                     "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
                r.raise_for_status(); d = r.json(); text = d["message"]["content"]
                meta["tokens_in"], meta["tokens_out"] = d.get("prompt_eval_count", 0), d.get("eval_count", 0)
            else:
                raise LLMUnavailable(f"unknown provider {settings.LLM_PROVIDER}")
            meta["latency_s"] = round(time.time() - t0, 3)
            meta["cost_usd"] = (meta["tokens_in"] * settings.COST_IN_PER_MTOK + meta["tokens_out"] * settings.COST_OUT_PER_MTOK) / 1e6
            return json.loads(text.strip().removeprefix("```json").removesuffix("```").strip()), meta
        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
            last = e; time.sleep(settings.RETRY_BACKOFF_S * (2 ** i))
    raise LLMTimeout(f"LLM failed after {meta['attempts']} attempts: {last}")


def _installed(model: str, names: list[str]) -> bool:
    base = model.split(":")[0]
    return any(n == model or (":" not in model and n.split(":")[0] == base) for n in names)


def status() -> dict:
    out = {"llm_provider": settings.LLM_PROVIDER, "chat_model": settings.OLLAMA_MODEL if settings.LLM_PROVIDER == "ollama" else (settings.ANTHROPIC_MODEL if settings.LLM_PROVIDER == "anthropic" else None),
           "embed_provider": settings.EMBED_PROVIDER, "embed_model": settings.EMBED_MODEL, "ollama_url": settings.OLLAMA_URL, "ollama_reachable": None, "installed_models": [],
           "chat_model_installed": None, "embed_model_installed": None, "error": None}
    if "ollama" in (settings.LLM_PROVIDER, settings.EMBED_PROVIDER):
        try:
            r = httpx.get(f"{settings.OLLAMA_URL}/api/tags", timeout=3); r.raise_for_status()
            names = [x["name"] for x in r.json().get("models", [])]; out.update(ollama_reachable=True, installed_models=names)
            if settings.LLM_PROVIDER == "ollama": out["chat_model_installed"] = _installed(settings.OLLAMA_MODEL, names)
            if settings.EMBED_PROVIDER == "ollama": out["embed_model_installed"] = _installed(settings.EMBED_MODEL, names)
        except Exception as e: out.update(ollama_reachable=False, error=str(e)[:120])
    return out
