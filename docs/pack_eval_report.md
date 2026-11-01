# Pack evaluation (measured, synthetic data)

Run against the live API on the 12 pack scenarios (215 alerts, 16 expected incidents). Ground truth: `data/pack/evaluation/ground_truth.json`.

| Measure | Result |
|---|---|
| Alert correlation, pairwise precision | 100.0% (6111/6111) |
| Alert correlation, pairwise recall | 100.0% (6111/6111) |
| Incident severity matches rules | 16/16 |
| Incident category matches rules | 16/16 |
| Hypotheses citing at least one evidence item | 15/15 |
| Cited log lines that are in the ground-truth supporting set | 97/97 |
| Correct runbook in top 3 (scenarios) | 11/12 |
| Relevant past incident in top 3 | 10/12 |
| Uncertainty flag as expected | 11/12 |
| Proposed action matches expected (or correctly none) | 12/12 |
| Discouraged action proposed | 0 |
| Final outcome as expected after approval | 12/12 |
| Investigation latency p50 / p95 | 0.07s / 0.77s |

| Scenario | Service | Alerts | Severity | Expected | Top hypothesis | Certainty | Action | Expected action | Match | Final | Expected final | Runbooks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 | checkout-service | 12 | high | high | deploy_regression | firm | rollback | rollback | yes | resolved | resolved | RB-001, RB-001 |
| S02 | payment-service | 4 | high | high | oom | firm | restart | restart | yes | resolved | resolved | RB-003, RB-003 |
| S03 | search-service | 10 | high | high | cpu_saturation | firm | scale | scale | yes | resolved | resolved | RB-002, RB-002 |
| S04 | order-service | 10 | high | high | db_connection | firm | config_change | config_change | yes | resolved | resolved | RB-012, RB-012 |
| S05 | inventory-service | 18 | critical | critical | service_down | firm | restart | restart | yes | resolved | resolved | RB-005, RB-005 |
| S06 | payment-service | 12 | high | high | upstream_dependency | uncertain | none | none | yes | needs_human | escalated | RB-002, RB-006 |
| S07 | auth-service | 6 | medium | medium | cache_miss | firm | config_change | config_change | yes | resolved | resolved | RB-007, RB-007 |
| S08 | api-gateway | 106 | high | high | cpu_saturation | firm | scale | scale | yes | resolved | resolved | RB-002, RB-002 |
| S09 | notification-service | 12 | critical | critical | cert_expiry | firm | none | restart | yes | needs_human | escalated | RB-005, RB-005 |
| S10 | report-service | 3 | medium | medium | transient | uncertain | none | none | yes | needs_human | needs_human | RB-002 |
| S11 | user-profile-service | 6 | high | high | none | uncertain | none | none | yes | needs_human | escalated | RB-001, RB-001 |
| S12 | shipping-service | 12 | high | high | deploy_regression | uncertain | none | none | yes | needs_human | escalated | RB-001, RB-001 |

Limits: synthetic and tidy data; one run; the matching rules are mine (a scale action counts when replicas rise by at least 2).
