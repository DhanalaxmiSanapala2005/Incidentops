---
doc_id: high_cpu_investigation
version: 2
category: cpu
access: engineer
recommended_action: scale
---
# High CPU investigation

## Symptoms
CPU above 90 percent, request queue growing, worker pool saturated, queue depth rising, latency elevated.

## Diagnosis
Check queue depth and worker saturation. Confirm no deployment in the last hour. Compare CPU per replica.

## Remediation
Scale the service out by two replicas (maximum 10). Do not scale if a deployment regression is suspected.

## Side effects
More replicas raise cost and open more database connections.

## Rollback plan
Scale back to the previous replica count.

## Verification
CPU below 80 percent and latency under 1 second for 5 minutes.
