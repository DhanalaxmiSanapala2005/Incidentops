---
doc_id: elevated_error_rate
version: 1
category: error_rate
access: engineer
recommended_action: config_change
---
# Elevated error rate

## Symptoms
5xx responses, NullPointerException, error rate above 5 percent, feature flag enabled, upstream bad gateway.

## Diagnosis
Group errors by endpoint and feature flag. Check for upstream dependency failures such as CDN 502 responses.

## Remediation
Disable the offending feature flag via an allowlisted configuration change. Upstream failures need escalation.

## Side effects
Flagged feature becomes unavailable to users.

## Rollback plan
Restore the previous flag value.

## Verification
Error rate below 5 percent.
