# Where things are (file map)

## 1. Incident data (alerts)
| What | File | Notes |
|---|---|---|
| 12 file-driven scenarios (bundled demo) | `data/pack/alerts/alerts.csv` (215 alerts), `data/pack/incident_test_workbook.xlsx` (same data as sheets) | Loaded by **Load Demo Scenario** or the **Load incident data pack** button (`backend/pack.py`) |
| Answer key (never read by the app) | `data/pack/evaluation/ground_truth.json` | Used only by tests and `scripts/run_pack_eval.py` |
| 10 older code-defined scenarios | `data/scenarios.py` | Still available under "Launch a single scenario" on the dashboard |
| SOC security alerts | `data/samples/real_alerts.xlsx`, `data/samples/synthetic_labelled_sample.csv` | Investigation-only track |
| Your own files | Data and import page | Alerts, logs, metrics, traces, deployments, runbooks, resolved incidents (see `/import/requirements`) |

## 2. Fake services that return logs, metrics, traces, deployments (the mock monitoring service)
| What | File |
|---|---|
| The service (FastAPI, port 8001): `/services/{name}/metrics, /logs, /traces, /deployments, /health, /state` and sandbox actions `/sandbox/...` | `integrations/mock_app.py` |
| Telemetry read from files (pack and uploads) | `integrations/pack_world.py`, files in `data/pack/telemetry/` (`logs.csv`, `metrics.csv`, `traces.csv`, `deployments.csv`) |
| Starting state of each service and what each action does (success, no effect, fails) | `data/pack/sandbox/sandbox_state.json`, `data/pack/sandbox/remediation_outcomes.json` |
| Old code-generated telemetry for the 10 legacy scenarios | `data/scenarios.py` |
| The client the backend uses (retries, timeouts, signed calls) | `integrations/client.py`, `common/signing.py` |

## 3. Knowledge for RAG (runbooks, playbooks, past incidents)
| What | Where |
|---|---|
| 13 versioned IT runbooks + 14 files (RB-001 has superseded v1) | `data/pack/knowledge/runbooks/` |
| 26 past resolved incidents | `data/pack/knowledge/resolved_incidents.json` |
| 9 older runbooks, 17 SOC playbooks, 38 older resolved incidents | `data/runbooks/`, `data/resolved_incidents.json` |
| Uploaded runbooks / resolved incidents | `data/uploads/` (created on first upload) |
| Retrieval code (keyword + optional Ollama embeddings, role filter, latest version only, injection sanitising) | `agents/rag.py`, `agents/embeddings.py` |
| Stored vectors | table `chunk_vectors` (migration 0003) |

## 4. The agents
| Agent | Code | Kind |
|---|---|---|
| Workflow (LangGraph graph: triage, investigate, retrieve, plan, verify, propose or escalate, audit) | `agents/graph.py` | orchestration, state saved after every node |
| Triage Agent | node `triage` in `agents/graph.py` + rules in `backend/rules.py` (severity, category) and correlation in `backend/core.py` (`ingest_alert`) | deterministic |
| Log Investigation Agent | node `investigate` in `agents/graph.py` + `agents/signals.py` (hypotheses from logs, metrics, deployments, traces) | deterministic heuristics; SOC alerts use `agents/soc.py` (small trained model) |
| Runbook Retrieval Agent | node `retrieve` in `agents/graph.py` + `agents/rag.py` | keyword + optional embeddings |
| Remediation Planner | node `plan` in `agents/graph.py` + `agents/planner.py` (options, risks, rollback) and `narrate` (LLM or template) | deterministic options; LLM only for wording |
| Approval gate and execution | `backend/main.py` (`/actions/{id}/approve`), `backend/remediation.py`, `backend/rules.py` (`validate_action`) | deterministic, human approval required |
| LLM (Ollama or Anthropic, optional) | `agents/llm.py` | explanations and chat wording only |
| Chat assistant (read-only) | `agents/chat.py` | deterministic with optional LLM rephrase |
