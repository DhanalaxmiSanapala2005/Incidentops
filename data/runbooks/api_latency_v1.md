---
doc_id: api_latency
version: 1
category: latency
access: engineer
recommended_action: rollback
---
# API latency spike

## Symptoms
Latency above 2 seconds, p95 elevated, timeouts, slow upstream, CPU rising with latency.

## Diagnosis
Correlate the latency start with deployments and database connection errors. Check cache hit ratio.

## Remediation
If a deployment preceded the spike, roll back. If cache misses dominate, raise cache TTL.

## Side effects
Rollback reverts recent features; cache TTL increases staleness.

## Rollback plan
Redeploy the rolled-back version or restore the TTL value.

## Verification
Latency under 1 second and error rate under 5 percent.
