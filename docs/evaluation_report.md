# Evaluation report

- Test set: 10 scenarios x 3 runs = 30 end-to-end workflows (inject -> investigate -> approve where applicable -> verify)
- Scenario pass rate: **30/30**
- Investigation workflow latency: **p50 0.057s, p95 0.576s** (n=30; includes mock-service HTTP calls and RAG; LLM provider here: see below)
- Full scenario wall time incl. approval/execution: p50 0.136s, p95 0.620s
- Workflow error rate: 0.0%; degraded-but-safe rate: 10.0%
- Tokens in/out: 0/0; average cost per task: $0.0

## Run 1 detail

| Scenario | Name | Severity | Proposed op | Final status | Latency (s) | Result |
|---|---|---|---|---|---|---|
| s01 | High CPU on worker pool | high | scale | resolved | 0.093 | PASS |
| s02 | Memory exhaustion in search | high | restart | awaiting_approval | 0.066 | PASS |
| s03 | Payment API latency spike after deploy | critical | rollback | resolved | 0.068 | PASS |
| s04 | Orders API errors from feature flag | high | config_change | resolved | 0.08 | PASS |
| s05 | Inventory service downtime | critical | restart | resolved | 0.057 | PASS |
| s06 | Duplicate alert storm on auth | medium | config_change | awaiting_approval | 0.076 | PASS |
| s07 | Billing errors after faulty deployment | high | rollback | awaiting_approval | 0.068 | PASS |
| s08 | Approved remediation succeeds (checkout) | medium | restart | resolved | 0.065 | PASS |
| s09 | Remediation fails and escalates (reports) | critical | restart | escalated | 0.055 | PASS |
| s10 | Monitoring outage and LLM timeout (media) | medium | escalate | needs_human | 0.576 | PASS |

## Limitations
- Latency/cost reflect the deterministic template narrative unless LLM_PROVIDER is configured; with a real LLM, re-run to measure model latency, tokens and cost.
- Services are mocks; recovery behaviour is simulated by scenario definitions.
- Retrieval is TF-IDF over a small synthetic corpus; use pgvector/Chroma embeddings at scale.
- Infrastructure severity, category and action rules are deterministic and unit-tested. The only trained model is the SOC true-positive triage model (synthetic labels).

## SOC alerts (measured)

- Test set: 68 imported security incidents (68 mapped to a playbook; 17 alert types; unmapped titles: none)
- Playbook retrieval Recall@1: **68/68 = 100.0%**, Recall@3: **68/68 = 100.0%** (TF-IDF over runbooks and resolved incidents)
- Grounded hypotheses (cite at least one evidence id): **68/68**
- Hypothesis mix: {'insufficient_evidence': 23, 'likely_false_positive': 24, 'likely_true_positive': 15, 'inconclusive': 6}; insufficient-evidence rate 33.8%
- Executable actions created for security alerts: **0** (expected 0: investigation-only by design)
- Caveat: the retrieval query includes the alert title, which matches the playbook name, so this mostly measures title matching. A description-only query would be a harder test and is not yet measured.
- Triage model quality on a held-out split: see `docs/soc_eval.md` (synthetic data).
