# Incident data pack (synthetic)

Everything here is **synthetic**: no real customers, logs or secrets. Generated deterministically (`python tools/build_pack.py <dir>`), checked by `python tools/validate_pack.py <dir>`.
Fake secrets and emails (for example `hunter2`, `jane.doe@example.com`) are planted on purpose to test redaction.

## Folder guide
| Path | What it is | Used for |
|---|---|---|
| `alerts/alerts.csv` | 215 alerts (cpu, memory, latency, error_rate, downtime) with duplicates | Alert intake, correlation, urgency |
| `alerts/invalid_alerts.csv` | 12 bad rows with `expected_error` | Validation messages, negative tests |
| `telemetry/metrics.csv` | 720 per-minute rows (cpu, memory, p95 latency, error rate, availability, request rate) | Metric evidence |
| `telemetry/logs.csv` | 1165 log lines with `log_id` and `trace_id` | Log evidence and citations |
| `telemetry/traces.csv` | 200 spans in 96 traces | Trace evidence |
| `telemetry/deployments.csv` | 31 deployment and config events with version history | Deployment evidence, rollback targets |
| `knowledge/runbooks/*.md` | 14 runbook files (13 playbooks; RB-001 has a superseded version 1) | RAG corpus, remediation planning |
| `knowledge/resolved_incidents.json` | 26 historical resolved incidents | RAG: similar incidents |
| `reference/` | services, external dependencies, urgency rules, users, roles, approval rules, action allowlist | Rules and authorization |
| `sandbox/` | service state per scenario and the result of each action per scenario | Mock remediation sandbox |
| `evaluation/` | `ground_truth.json`, `rag_eval_queries.json` (41 queries), `negative_tests.json`, `tfidf_baseline_results.json` | Measuring quality |
| `security_fixtures/poisoned_runbook.md` | A runbook containing a prompt injection | Retrieval security test |
| `incident_test_workbook.xlsx` | alerts, logs, metrics, traces, deployments, services as sheets | Review in Excel and upload tests |
| `pack_stats.json` | counts produced by the validator | Reporting |

## Scenarios (12)
| ID | Story | Service | Root cause type | Expected action | Expected outcome | Alerts |
|---|---|---|---|---|---|---|
| S01 | Bad deployment raises checkout error rate | checkout-service | deployment | rollback | resolved | 13 |
| S02 | Memory leak in payment-service | payment-service | resource | restart | resolved | 4 |
| S03 | CPU saturation during a traffic spike (with injected log text) | search-service | resource | scale | resolved | 11 |
| S04 | Latency from database connection pool exhaustion | order-service | config | config_change | resolved | 10 |
| S05 | Inventory service down in an OOM crash loop | inventory-service | resource | restart | resolved | 18 |
| S06 | Payment errors caused by a third party outage | payment-service | dependency | none (escalate) | escalated | 13 |
| S07 | Auth latency after a cache TTL configuration change | auth-service | config | config_change | resolved | 6 |
| S08 | API gateway alert storm | api-gateway | resource | scale | resolved | 106 |
| S09 | Failed remediation: expired certificate (restart does not help) | notification-service | secret_expiry | restart | escalated | 13 |
| S10 | Noisy flapping latency alert | report-service | noise | none (escalate) | needs_human | 3 |
| S11 | Telemetry outage during an incident | user-profile-service | unknown | none (escalate) | escalated | 6 |
| S12 | Shipping latency: recent deployment is a red herring | shipping-service | dependency | none (escalate) | escalated | 12 |

## Rules the data follows
- Severity: cpu 80/95 percent, memory 85/95 percent, latency 1000/4000 ms, error rate 5/10 percent (medium/high); downtime is always critical. An incident takes the highest alert severity, one level higher when 3 or more distinct metrics breach. Same as the application rules.
- Correlation: alerts for the same service within 30 minutes of the incident opening belong to one incident (the application's CORRELATION_WINDOW_MIN); same service and metric repeated is a duplicate (kept as evidence). Four alerts on other services are deliberate noise (separate incidents).
- Alert files do **not** contain the answer. The expected grouping is only in `evaluation/ground_truth.json`.
- Runbook front matter: `doc_id, version, status (current|superseded), title, category, access, recommended_action`.
- Allowed actions: restart, rollback, scale (1 to 10), config_change (3 allowlisted keys). Parameters: `service`, `target_version`, `replicas`, `key`, `value`.

## Known limits
- Synthetic and tidy compared with real telemetry. Quality numbers measured on it show the pipeline works, not production accuracy.
- Telemetry covers only the primary service of each scenario (dependencies appear in traces and logs).
- Dates are fixed in October 2026 so results are reproducible.

- Mock sandbox rule: a `scale` action succeeds when replicas increase by at least 2 over the scenario's starting count; rollback must target the previous version; config changes must match the key and value in `sandbox/remediation_outcomes.json`.
