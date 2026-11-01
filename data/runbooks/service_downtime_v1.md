---
doc_id: service_downtime
version: 1
category: downtime
access: engineer
recommended_action: restart
---
# Service downtime

## Symptoms
Health checks failing, liveness probe failed, process exited, CrashLoopBackOff, no space left on device.

## Diagnosis
Read the last logs before exit. Check disk space and exit codes. Disk-full cases are not fixed by a restart.

## Remediation
Restart the service. If it fails again, escalate to the platform on-call engineer.

## Side effects
Brief outage while the container restarts.

## Rollback plan
Not reversible. Escalate if health does not return.

## Verification
Health endpoint reports healthy for 3 consecutive checks.
