# Deployment notes
**Local, no Docker:** see README (three processes, SQLite). **Docker:** `cp .env.example .env && docker compose up --build` (PostgreSQL, mock service, API with `alembic upgrade head`, UI). The Compose file has not been run in the authoring environment, so verify it on your machine.

**Before any shared deployment:**
- Replace `SECRET_KEY`, `SANDBOX_SIGNING_KEY`, `MOCK_SERVICE_KEY` and the seeded demo passwords (admin123 etc.). Put secrets in the platform secret store, not in git.
- Terminate TLS in front of API and UI; restrict the API port.
- Set `LLM_PROVIDER` (anthropic or ollama) and its key. Re-run `scripts/run_eval.py` to measure real latency, tokens and cost.
- Tracing: set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` (LangGraph traces automatically). Inputs/outputs are hidden by default; unhide only for non-sensitive data. Not verified against a live LangSmith project here.
- Workers: investigations can run in an in-process background task (`/investigate/async`). For multi-instance production use a durable queue (Celery/RQ/SQS). A crash mid-run leaves the run marked `running` for 10 minutes before a retry is allowed.
- AWS sketch: ECR images, ECS Fargate (api, ui, mock), RDS PostgreSQL, Secrets Manager, ALB with TLS.
