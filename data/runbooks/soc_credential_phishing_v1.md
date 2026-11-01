---
doc_id: soc_credential_phishing
version: 1
category: security
access: engineer
recommended_action: none
---
# Credential Phishing

## Alert names
Credential Phishing

## Symptoms
This alert fires when a user receives an email containing a link to a fake login page designed to steal their password. The investigation focuses on confirming whether the link is genuinely malicious, whether anyone actually entered credentials, and how far the exposure has spread.

## Diagnosis
1. Sender and link reputation Check whether the sender domain is real or spoofed, and look up the link against known-bad reputation sources.
2. Recipient scope Determine how many users received the email — a single-target case is handled very differently from an org-wide blast.
3. Click and login activity Check whether anyone actually clicked the link, and if so, whether a login attempt followed from a new location afterward.
4. Post-click account changes For anyone who clicked, check for a new inbox forwarding rule or a new OAuth app consent immediately afterward — either is a strong sign the account is already compromised, not just exposed.
5. Scope and containment Find every recipient across mail logs, block the sender, URL, and IP at the gateway, and force a password reset plus new MFA for anyone who clicked.

## Remediation
Revoke active sessions and force MFA re-registration for the affected account (simulated; not yet automated in the sandbox). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
User is signed out of all devices and must sign in again.

## Rollback plan
Re-enable the account sessions; no data is deleted.

## Verification
No new sign-ins from the flagged IP and no new mailbox rules or MFA changes for 24 hours.
