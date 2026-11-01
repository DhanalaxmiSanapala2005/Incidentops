# Requirements: BRD, SRS, user stories and acceptance matrix

## 1. Business requirements (BRD)
- **Problem:** responders spend hours correlating alerts, logs, deployments and runbooks.
- **Objective:** an assistant that correlates alerts, proposes evidence-cited root causes and remediation, and executes only approved, allowlisted sandbox actions.
- **Success measures:** related alerts clustered with no evidence lost; every hypothesis cites evidence or is marked uncertain; zero mutating calls without approval; MTTR, repeated-alert and outcome dashboards; measured p50/p95 latency, error rate, tokens and cost (`docs/evaluation_report.md`).
- **Scope:** infrastructure incidents (5 alert metrics, 10 scenarios) and SOC security alerts (17 alert types, investigation only).
- **Out of scope:** real production infrastructure, real customer data, automatic SOC containment.

## 2. Software requirements (SRS)
| ID | Requirement | Kind |
|---|---|---|
| FR1 | Ingest alerts for error rate, latency, CPU, memory, downtime (API, scenario, file) | Functional |
| FR2 | Collect logs, metrics, traces, deployments from sandbox services via mock telemetry API | Functional |
| FR3 | Correlate duplicates into incidents, classify urgency by documented rules | Functional |
| FR4 | Retrieve versioned runbooks and resolved incidents (RAG) under role-based access | Functional |
| FR5 | Generate root-cause hypotheses citing evidence; flag uncertainty; say so when evidence is insufficient | Functional |
| FR6 | Propose options with risk, side effects, rollback | Functional |
| FR7 | Engineer approval for restart, rollback, scale, config change | Functional |
| FR8 | Execute only allowlisted sandbox operations, record each call, verify health, roll back or escalate | Functional |
| FR9 | Timelines, post-incident reports, dashboards (MTTR, repeated alerts, outcomes), CSV export | Functional |
| FR10 | Optional import of alert files with schema detection and row-level validation | Functional |
| FR11 | Read-only conversational assistant with evidence citations that refuses state-changing requests | Functional |
| NFR1 | Backend-enforced RBAC (401/403), Pydantic validation, secrets from environment | Security |
| NFR2 | Redaction of secrets/emails/IPs; prompt-injection sanitising; fail closed | Security |
| NFR3 | Bounded retries, timeouts, LLM fallback, safe escalation on outage | Reliability |
| NFR4 | Audit record per approval and state change (actor, time, tool result) | Compliance |
| NFR5 | Structured JSON logs with request ids; workflow latency, token and cost metrics | Observability |
| NFR6 | Alembic migrations match models (checked); Docker Compose for local run | Deployment |

## 3. User stories
- As a **responder**, I load a scenario and see alerts clustered into one incident so I do not triage duplicates by hand.
- As a **responder**, I open an investigation and see hypotheses with linked evidence, uncertainty and the runbook used.
- As an **engineer**, I review risk and rollback for a proposed action, then approve or reject with a comment.
- As an **engineer**, I see the sandbox result and health verification, and an automatic rollback or escalation on failure.
- As a **SOC analyst**, I import an alert file and get the matching playbook and an evidence-cited estimate, or a clear statement that evidence is insufficient.
- As an **admin**, I review the audit log, approval history, policy checks and settings.
- As a **responder**, I ask the assistant questions in plain language and get cited answers; if I ask it to restart or approve something it refuses and points me to the approval queue.
- As a **viewer**, I read incidents and reports but cannot change anything.

## 4. Acceptance matrix
See `docs/DESIGN.md` (Acceptance matrix) for requirement-to-code-to-test rows. Current suite: 88 pytest tests plus `scripts/ui_smoke.py`.
