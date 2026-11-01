---
doc_id: soc_impossible_travel_activity_detected
version: 1
category: security
access: engineer
recommended_action: none
---
# Impossible Travel Activity Detected

## Alert names
Impossible Travel Activity Detected

## Symptoms
This alert fires when the same user account signs in from two locations that are too far apart to have been reached through normal travel in the time between the two sign-ins. The investigation focuses on whether this reflects genuine account compromise or a benign explanation such as VPN use, real travel, or a cloud proxy.

## Diagnosis
1. Previous authentication Look back through the user's recent sign-in history to see whether this location, IP address, or pattern has shown up before. A recurring pattern (regular travel, a known VPN exit point) supports a benign explanation, while a location or network the account has never used before raises suspicion.
2. User activity Review what the account did immediately after the flagged sign-in. Routine, role-consistent activity is a good sign, but anything like a new mailbox rule, a bulk file download, or a change to MFA settings right after the sign-in is a strong indicator that the account has been taken over.
3. IPs Check the reputation and origin of the IP addresses involved. An IP that resolves to a known corporate VPN or a confirmed travel itinerary supports benign activity, while an IP flagged as a Tor exit node, anonymizing proxy, or known-malicious infrastructure should be treated as a serious warning sign.
4. Prior information on user Bring in context about the user themselves — their role, whether they travel for work, and whether they are a privileged account such as a domain or global admin. A travelling sales rep with manager confirmation can usually be closed quickly, while an unexpected login on a privileged account should be treated as high priority regardless of other signals.

## Remediation
Revoke active sessions and force MFA re-registration for the affected account (simulated; not yet automated in the sandbox). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
User is signed out of all devices and must sign in again.

## Rollback plan
Re-enable the account sessions; no data is deleted.

## Verification
No new sign-ins from the flagged IP and no new mailbox rules or MFA changes for 24 hours.
