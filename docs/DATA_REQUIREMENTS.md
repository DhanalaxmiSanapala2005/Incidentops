# Data and dependency checklist: status in this build

| # | Input | Status | Where |
|---|---|---|---|
| 1 | Alert data, 10+ reproducible scenarios, 3+ categories | **Done (synthetic)** plus your real SOC alerts | `data/scenarios.py` (10 scenarios, 5 metrics); `data/templates/alerts_infra_template.csv` (26 alerts with the suggested columns); `data/samples/real_alerts.xlsx` (your file, 17 alert types) |
| 2 | Runbooks / playbooks | **Done** | 9 infrastructure runbooks + **17 SOC runbooks built from your `SOC_Alert_Playbook.docx`** (`data/runbooks/soc_*`). Investigation steps are yours. Remediation, side effects, rollback and verification for SOC are **synthetic additions**, labelled as such |
| 3 | Logs, metrics, traces, deployments | **Done (mock telemetry API)** for infrastructure scenarios. SOC alerts carry their own evidence (alert, identity, indicators) | `integrations/mock_app.py` |
| 4 | Resolved-incident knowledge base | **Done (synthetic)** | `data/resolved_incidents.json`: infrastructure incidents plus 34 SOC entries (one confirmed and one benign per playbook), all labelled synthetic |
| 5 | Roles and approval rules | **Done**, see `docs/ROLES_AND_APPROVAL_RULES.md` | enforced in `backend/security.py` and `backend/main.py` |
| 6 | Two functioning integrations | **Done (mock)**: telemetry service and remediation sandbox, both with timeouts, retries and signed requests | `integrations/`, `common/signing.py` |

## Files per feature
Nothing is required for demo mode. Upload is optional and validated per row. See the **Data and import** page.

## Gaps and honest limits
- Your `real_alerts.xlsx` has only the 19 base SIEM columns, so no sign-in history, IP reputation or sandbox verdicts. The app therefore reports "insufficient evidence" for those alerts instead of guessing.
- `synthetic_train.xlsx` is synthetic. The triage model's metrics (`docs/soc_eval.md`) show the pipeline works, not real-world accuracy.
- Security alerts are **investigation-only**: no containment action (disable account, isolate host, block IP) is executed. The sandbox only supports restart, rollback, scale and config change for infrastructure services. Adding SOC containment ops is the next step.
- LangSmith tracing is still not wired in.
