# Roles and approval rules (enforced by the backend)

| Capability | viewer | engineer | admin |
|---|---|---|---|
| View incidents, reports, dashboards | yes | yes | yes |
| Import alerts, inject scenarios, run AI investigation | no | yes | yes |
| Approve or reject proposed actions | no | yes | yes |
| Retrieve engineer-level runbooks (RAG) | no | yes | yes |
| Retrieve admin-only runbooks (e.g. credential rotation) | no | no | yes |
| Use the read-only incident assistant (own private history) | yes | yes | yes |
| See runbook text in assistant answers | no (titles only) | yes | yes |
| Audit log, users and roles, settings, reset | no | no | yes |

- **Analyst** is not a separate role: `engineer` covers analyst and approver duties.
- **Approval rules:** every state-changing action (restart, rollback, scale, config change) needs approval from an engineer or admin. Actions expire after the approval window (default 30 min). Per-operation tiers (for example, only admins approve rollbacks) are **not** implemented.
- **Separation of duties:** when enabled in Settings, the person who triggered the investigation cannot approve its action.
- Missing or invalid token gives 401; wrong role gives 403; failed verification triggers rollback or escalation. All decisions are written to the audit log.
