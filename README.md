# IncidentOps AI: Autonomous IT Incident Management

Streamlit UI + FastAPI + PostgreSQL + LangGraph agents + RAG + mock monitoring/sandbox services.
Alerts are correlated into incidents, investigated with cited evidence, and fixed **only** after an engineer approves an allowlisted sandbox action, which is then verified (or reverted/escalated).

## Run (no Docker, SQLite)
```bash
./run_local.sh            # mock :8001, API :8000 (docs at /docs), UI :8501
```
Or Docker (PostgreSQL): `cp .env.example .env && docker compose up --build`

Demo logins: `admin/admin123`, `engineer/engineer123`, `engineer2/engineer123`, `viewer/viewer123`.

## 2-minute demo
1. Sign in as **engineer** > Dashboard > pick `s03 Payment API latency spike` > *Inject alerts*.
2. **AI investigation** > *Run investigation*: see hypotheses (with evidence ids and uncertainty), metrics, redacted logs, runbooks, options.
3. **Approval queue** > *Approve and execute*: the sandbox rolls back, health is verified, the incident resolves.
4. Failure path: inject `s09` > investigate > approve: the restart does not help, so the incident is **escalated** and no further changes are made.
5. Sign in as **admin** > Admin: audit log, p50/p95, roles, settings, reset.

## Tests and evaluation
```bash
PYTHONPATH=. pytest -q                       # 36 tests (rules, correlation, 10 scenarios, approval/RBAC/security, resilience)
PYTHONPATH=. python scripts/ui_smoke.py      # drives the real Streamlit pages (stack must be running)
PYTHONPATH=. python scripts/run_eval.py      # 10 scenarios x 3 runs -> docs/evaluation_report.md
```

## LLM
Default `LLM_PROVIDER=none` uses a deterministic template narrative (everything works offline). Set `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`, or `ollama`, to have a model write the explanations. The model never chooses the action; figures it cites must exist in the evidence or its text is discarded.

## Layout
`frontend/` Streamlit (role-aware navigation, 5 areas) · `backend/` API, rules, security, remediation · `agents/` LangGraph, signals, RAG, planner, LLM client · `integrations/` mock monitoring + sandbox · `data/` scenarios + runbooks · `migrations/` Alembic · `docs/` design, Postman, evaluation.
See `docs/DESIGN.md` for agent specs, ERD, sequence diagram, security controls and the acceptance matrix.

## Known limitations (honest list)
- Investigations run synchronously inside the request (fast here); there is no job queue/worker. Add Celery/RQ for long agent tasks.
- Real-LLM mode is implemented but was **not exercised** in development (no API key); the fallback and timeout paths are tested.
- PostgreSQL/Docker files are provided; automated tests ran on SQLite (the Alembic migration was generated and applied on SQLite).
- Hypothesis detection is rule-based; there is no trained ML model. Retrieval is TF-IDF, not embeddings.
- LangGraph state is persisted to the database after each node; the in-memory LangGraph checkpointer is not used.
- Not covered: real cloud infrastructure, SSO, CSRF/rate limiting, TLS (put behind a reverse proxy), secrets manager.


## SOC alerts, playbooks and your data files (added)
- **Load Demo Scenario** now also loads one alert per SOC type from `data/samples/real_alerts.xlsx` and investigates it.
- **Data and import** page: bundled samples, optional upload (.xlsx/.csv/.json, 15 MB), "Validate only" dry run, rejected rows reported with row numbers.
- SOC playbooks (`data/runbooks/soc_*`) are built from your docx: `python scripts/build_soc_assets.py path/to/SOC_Alert_Playbook.docx`.
- Triage model: `pip install -r requirements-train.txt && python scripts/train_soc_model.py path/to/synthetic_train.xlsx` (writes `data/soc_model.json` and `docs/soc_eval.md`).
- Measured on a 1,800-row held-out split of the synthetic file: severity-only baseline F1 0.601, model F1 0.768, ROC AUC 0.875. Synthetic data, see `docs/soc_eval.md`.
- Security incidents end as `needs_human`: the AI gives an evidence-cited estimate and the playbook, and never executes containment.
- See `docs/DATA_REQUIREMENTS.md` and `docs/ROLES_AND_APPROVAL_RULES.md`.


## Incident assistant (chat)
Open **Assistant** in the sidebar, pick an incident and ask in plain language: "Why did this happen?", "Show the logs", "What does the runbook say?", "What actions are proposed?", "Show the timeline", or portfolio questions like "What incidents are open?" and "What is the MTTR?".
- **Read-only by design:** requests to approve, reject, restart, roll back, scale or resolve are refused, audited as `blocked`, and pointed to the Approval queue. Chat code only reads the database.
- **Grounded:** answers are built from stored investigations with evidence citations (`[E12]`, `[RB doc@v1]`, `[A3]`); hypotheses are labelled as not confirmed; "insufficient evidence" is stated when that is the case.
- **Optional LLM:** with `LLM_PROVIDER` set, the LLM may only rephrase the answer. Output is discarded if it adds numbers or drops citation tags; on timeout the rules answer is used.
- **Governance:** any signed-in role may ask; viewers do not see runbook text; messages are redacted, stored per user (private, clearable), rate-limited to 20 per minute.
- API: `POST /chat`, `GET /chat/history`, `DELETE /chat/history`.


## Incident data pack, uploads and local Ollama (current)
- **Load Demo Scenario** loads `data/pack` (12 scenarios as files: alerts, logs, metrics, traces, deployments, runbooks, past incidents), investigates every incident and adds the SOC sample. Nothing needs uploading.
- **Data and import** page: load the pack, download the sample files (including `incident_test_workbook.xlsx`), or upload your own alerts, logs, metrics, traces, deployments (tables, auto-detected), runbooks (.md, admin) and resolved incidents (admin). Every upload has a preview, a validate-only option and row-level errors.
- File map: `docs/WHERE_THINGS_ARE.md`. Measured results: `docs/pack_eval_report.md` (workflow on 12 scenarios) and `docs/rag_eval_report.md` (retrieval).
- Local Ollama (optional): `ollama pull llama3.1`, `ollama pull nomic-embed-text`, set `LLM_PROVIDER=ollama` (embeddings turn on automatically), restart the API, check with `python scripts/check_ollama.py`, then use **Models and RAG** (admin) to test and rebuild the search index. If Ollama is off, the app uses templates and keyword search. The Ollama path is tested with stand-in models only, not a live model.
- Tests: `pytest -q` (116 tests) and `python scripts/ui_smoke.py` (with the services running).
