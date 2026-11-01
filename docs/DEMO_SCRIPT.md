# Demo script (about 12 minutes)
Start mock service (8001), API (8000), UI (8501). Sign in as `admin` first.

1. **(1 min) Overview.** Click **Load Demo Scenario**. Show KPIs, alert volume (unique vs duplicate), service health, safety controls.
2. **(2 min) Correlation.** Incident records: open the alert-storm scenario. Show duplicates flagged, source alerts kept, timeline.
3. **(3 min) Success path.** AI investigation on the bad-deployment incident (s03). Show hypotheses with evidence ids and the uncertain one, retrieved runbook and prior incident, options with risk and rollback. Sign in as `engineer`, Approval queue: approve rollback. Show sandbox result, health verification, resolved status, MTTR.
4. **(2 min) Failure path.** Scenario s09: approve restart, it fails verification, system escalates. Also reject one action and show nothing executed.
5. **(1 min) Authorization.** As `viewer` the approval page is blocked; show a 403 in `/docs`.
6. **(1 min) Resilience.** Scenario s10: monitoring outage and LLM timeout produce a degraded but safe escalation, with no invented diagnosis.
7. **(1 min) SOC alerts.** Open a security incident: playbook retrieved, "insufficient evidence" for base-field alerts, a scored estimate for the labelled sample. Show 0 executable actions.
8. **(1 min) Assistant.** Open Assistant on the s03 incident: ask "Why did this happen?" (cited hypotheses), "What actions are proposed?", then type "approve action 1" and show the refusal and the `blocked` audit entry. Switch to `viewer`: runbook text is hidden.
9. **(1 min) Governance.** AI governance: audit events, blocked actions, approval history, evidence coverage, tracing status. Admin page: p50/p95, error rate, cost.
10. **Reset:** Admin > Environment, or `POST /admin/reset`.
