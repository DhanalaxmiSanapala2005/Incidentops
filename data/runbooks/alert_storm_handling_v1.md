---
doc_id: alert_storm_handling
version: 1
category: latency
access: engineer
recommended_action: config_change
---
# Alert storm and cache miss handling

## Symptoms
Many duplicate alerts, token cache miss ratio high, slow identity provider, repeated latency alerts.

## Diagnosis
Group duplicates by service and metric; check cache miss ratio and upstream provider latency.

## Remediation
Increase cache TTL to 600 seconds through an allowlisted configuration change.

## Side effects
Cached values may be stale for up to 10 minutes.

## Rollback plan
Restore the previous cache TTL.

## Verification
Cache miss ratio below 0.3 and latency under 1 second.
