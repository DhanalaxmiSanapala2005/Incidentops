"""Checks local Ollama for this project. Usage: python scripts/check_ollama.py   (set LLM_PROVIDER / EMBED_PROVIDER / OLLAMA_MODEL / EMBED_MODEL first)"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents import embeddings, llm
s = llm.status(); print(json.dumps(s, indent=1)); ok = True
if s["ollama_reachable"] is None: print("\nNeither LLM_PROVIDER nor EMBED_PROVIDER is 'ollama'; nothing to check."); sys.exit(0)
if not s["ollama_reachable"]: print("\nOllama is not reachable. Start it (the Ollama app, or `ollama serve`) and check OLLAMA_URL."); sys.exit(1)
if s["chat_model_installed"] is False: print(f"\nRun: ollama pull {s['chat_model']}"); ok = False
if s["embed_model_installed"] is False: print(f"\nRun: ollama pull {s['embed_model']}"); ok = False
if ok:
    try: print("\nchat:", llm.complete_json('Reply only with JSON {"ok": true}', "ping")[1])
    except llm.LLMUnavailable as e: print("\nchat test failed:", e); ok = False
    try: print("embeddings:", len(embeddings.embed(["ping"])[0]), "dimensions")
    except embeddings.EmbeddingUnavailable as e: print("embeddings test failed:", e); ok = False
print("\nOK" if ok else "\nNOT READY"); sys.exit(0 if ok else 1)
