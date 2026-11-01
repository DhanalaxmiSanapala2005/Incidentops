# Assignment deliverables: status (honest)
| Deliverable | Status |
|---|---|
| Requirements, user stories, acceptance matrix | `docs/BRD_SRS.md`, `docs/DESIGN.md` |
| Architecture, agent graph, ERD, sequence diagrams | `docs/DESIGN.md` (text/Mermaid; render and export images for submission) |
| Streamlit app, FastAPI, agents, migrations, tests, README | Done; 88 tests pass; Alembic matches models |
| Synthetic seed data and evaluation fixtures | 10 scenarios, templates, SOC samples, KB, `scripts/run_eval.py`, `scripts/run_soc_eval.py` |
| OpenAPI, examples, Postman | `/docs`, `docs/IncidentOps.postman_collection.json` (includes import samples and background investigation; file upload `POST /import/alerts` is multipart, try it in `/docs`) |
| Docker, env sample, deployment | Files present; **Compose not run in my environment** |
| Evaluation report | `docs/evaluation_report.md` (measured, synthetic) |
| Demo | `docs/DEMO_SCRIPT.md` (you record it) |

## Known gaps against the assignment
- LangSmith tracing is configured by environment only and **unverified with a live key**; Langfuse not implemented.
- LLM metrics (tokens, cost) are 0 until a real provider is configured; the default narrative is a template.
- Background processing is in-process, not a durable queue.
- RAG is TF-IDF, not embeddings or a vector database.
- SOC alerts are investigation-only; no sandbox containment actions for them.
- Reference data for the SOC model is synthetic.

- Chat intent routing is keyword-based (21 regression cases pass); unusual phrasing falls back to a summary or help text. The LLM rephrase path is tested with a stubbed provider only, not a live model.


## Update: data pack wired in, RAG v2, Ollama
- Telemetry now comes from files (`data/pack/telemetry`) through the mock service; uploads for every file type; 116 tests pass; the workflow on 12 scenarios is measured in `docs/pack_eval_report.md`.
- RAG: hybrid keyword + embeddings (Ollama), stored in the database (`chunk_vectors`), role filter, latest version only. **Embedding quality has not been measured here** (no Ollama in the build environment): run `python scripts/run_rag_eval.py` on your machine.
- Still open: LangSmith traces unverified with a live key; Langfuse not implemented; background jobs are in-process; SOC alerts are investigation-only; data is synthetic.
