---
doc_id: soc_database_mass_export
version: 1
category: security
access: engineer
recommended_action: none
---
# Database Mass Export

## Alert names
Database Mass Export

## Symptoms
This alert fires when an insider runs an unusually large query or export against a production database, often pulling far more data than their role would normally require. The investigation focuses on whether this reflects legitimate analytics work or a deliberate attempt to remove sensitive data.

## Diagnosis
1. Scope and content Check the volume of the export and what kind of data it contains — PII, financial records, or intellectual property raise the stakes considerably over routine data.
2. Access pattern Determine whether the user is querying tables they don't normally touch as part of their role.
3. Destination Check whether the export went to a local file or was sent to another system, since that shapes how recoverable the situation is.
4. Timing and repetition Look at whether the query ran outside normal working hours, and whether this is a repeated pattern rather than an isolated incident.
5. User context Check the user's role and, notably, whether they are in the process of leaving the organization — departure status materially changes how this case should be prioritized.
6. Response Restrict database access pending review, involve HR/Legal, and audit exactly what was exported so the exposure is fully understood, not just flagged.

## Remediation
Suspend the user's access to the data source and notify the data owner (simulated). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
User cannot work with the affected data until access is restored.

## Rollback plan
Restore access after the owner confirms the activity was legitimate.

## Verification
No further bulk reads or exports and owner sign-off recorded.
