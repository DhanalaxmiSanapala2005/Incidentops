---
doc_id: deployment_rollback
version: 1
category: error_rate
access: engineer
recommended_action: rollback
---
# Deployment rollback procedure

## Symptoms
Errors started right after a deployment, schema mismatch, regression after release, faulty deployment.

## Diagnosis
Confirm the deployment timestamp precedes the first alert and errors reference the new release.

## Remediation
Roll back to the previous successful version listed in deployment history.

## Side effects
Reverts the release's features and fixes.

## Rollback plan
Roll forward by redeploying the release once fixed.

## Verification
Error rate normal and health checks green after the rollback.
