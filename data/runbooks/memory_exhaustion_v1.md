---
doc_id: memory_exhaustion
version: 1
category: memory
access: engineer
recommended_action: restart
---
# Memory exhaustion

## Symptoms
OutOfMemoryError, heap usage above 90 percent, GC overhead limit exceeded, memory leak, container OOM kill.

## Diagnosis
Inspect heap usage trend and GC logs. Check whether memory grows monotonically since the last start.

## Remediation
Restart the service to reclaim memory, then open a ticket for the leak.

## Side effects
About 30 seconds of interruption; in-flight requests are dropped.

## Rollback plan
Restart is not reversible. If unhealthy afterwards, escalate to on-call.

## Verification
Memory below 85 percent after restart and health check passing.
