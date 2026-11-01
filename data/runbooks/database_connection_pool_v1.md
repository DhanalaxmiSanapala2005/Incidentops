---
doc_id: database_connection_pool
version: 1
category: latency
access: engineer
recommended_action: rollback
---
# Database connection pool exhaustion

## Symptoms
db connection timeout, connection pool exhausted, pool at 100, waiting connections, error rate and latency after a deployment.

## Diagnosis
Compare pool usage before and after the latest deployment. A new release leaking connections is the usual cause.

## Remediation
Roll back to the previous known-good version. Do not raise pool size first; it hides the leak.

## Side effects
Reverts features in the faulty release; schema changes may not be backward compatible.

## Rollback plan
Redeploy the faulty version only after the leak is fixed.

## Verification
Pool usage under 60 percent and errors cleared.
