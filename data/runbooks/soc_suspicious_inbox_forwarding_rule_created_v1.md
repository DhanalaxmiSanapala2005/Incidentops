---
doc_id: soc_suspicious_inbox_forwarding_rule_created
version: 1
category: security
access: engineer
recommended_action: none
---
# Suspicious Inbox Forwarding Rule Created

## Alert names
Suspicious Inbox Forwarding Rule Created

## Symptoms
This alert fires when a mailbox rule is created that automatically forwards or redirects incoming mail, which is one of the most common ways attackers maintain access to a mailbox after a compromise. The investigation focuses on confirming who created the rule, where mail is going, and whether the activity looks legitimate.

## Diagnosis
1. User account & forwarded account info Identify the mailbox owner and compare it against where the rule is forwarding mail to. A rule that sends the owner's mail to their own known personal account with a documented reason is very different from one quietly forwarding to an unfamiliar external address.
2. Type of forwarding rule Look at exactly how the rule is configured — whether it forwards or redirects, whether it keeps a copy in the original mailbox or deletes it, and whether it only targets certain messages, such as ones containing words like “invoice” or “payment.” Rules that silently delete the original and target financial keywords are a classic sign of business email compromise.
3. Source IP Check the IP address the rule was created from against the user's normal sign-in pattern. If it matches their usual working IP and they confirm making the change themselves, it's likely benign. If it's a new or unfamiliar IP, especially following a recent suspicious sign-in, treat the account as likely compromised.

## Remediation
Purge the message from mailboxes, block the sender or URL and remove malicious mailbox rules (simulated). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
Legitimate mail from the same sender may be delayed or blocked.

## Rollback plan
Release the quarantined message and unblock the sender or URL.

## Verification
No further delivery from the sender and no rule forwarding to external addresses.
