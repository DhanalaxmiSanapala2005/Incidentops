---
doc_id: soc_service_account_token_abuse_k8s_cloud
version: 1
category: security
access: engineer
recommended_action: none
---
# Service Account Token Abuse (K8s/Cloud)

## Alert names
Service Account Token Abuse (K8s/Cloud)

## Symptoms
This alert fires when an attacker steals a service account's JWT or token from a pod or instance metadata service, using it to gain broader cluster or cloud access than a compromised user account alone would provide. The investigation focuses on how the token was obtained, how far it's been used, and cutting off that access path.

## Diagnosis
1. Origin of access Check whether the service account was authenticated from outside the cluster, and whether instance metadata was accessed from a pod that shouldn't have needed it.
2. Scope and reach Determine what the stolen token actually has permission to touch — a broadly scoped token is a materially bigger problem than a narrowly scoped one.
3. Usage pattern Look at the API calls made using the service account for anything anomalous relative to its normal behavior.
4. Lateral movement Check whether the token was used to move laterally into other cloud resources or cluster namespaces beyond its origin point.
5. Persistence Check whether the attacker created any persistence tied to the service account identity itself.
6. Containment Rotate the affected service account tokens immediately, tighten workload identity configuration (IRSA or equivalent), and add egress restrictions on the originating pods to prevent a repeat.

## Remediation
Revoke active sessions and force MFA re-registration for the affected account (simulated; not yet automated in the sandbox). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
User is signed out of all devices and must sign in again.

## Rollback plan
Re-enable the account sessions; no data is deleted.

## Verification
No new sign-ins from the flagged IP and no new mailbox rules or MFA changes for 24 hours.
