---
doc_id: soc_email_spoofing
version: 1
category: security
access: engineer
recommended_action: none
---
# Email Spoofing

## Alert names
Email Spoofing

## Symptoms
This alert fires when an email is crafted to appear as though it came from someone it didn't, often failing SPF, DKIM, or DMARC checks. The investigation focuses on confirming the spoof, understanding who it targeted, and whether it's part of a larger phishing or BEC attempt.

## Diagnosis
1. Authentication results Check the SPF, DKIM, and DMARC results, and compare the visible “From” header against the actual envelope sender for a mismatch.
2. Targeting pattern Identify who received the spoofed message — a spoof aimed at finance or HR is more concerning than a random target, since it suggests a BEC setup.
3. Reply-to and domain checks Look at whether the reply-to domain differs from the “From” domain, and whether an internal address was spoofed from an external source.
4. Downstream connection Check whether this spoof is linked to a broader phishing or BEC campaign already in progress.
5. Response Tighten the DMARC policy toward enforcement (p=reject), add explicit anti-spoof rules for the abused domain, and notify the spoofed party if it's external.

## Remediation
Purge the message from mailboxes, block the sender or URL and remove malicious mailbox rules (simulated). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
Legitimate mail from the same sender may be delayed or blocked.

## Rollback plan
Release the quarantined message and unblock the sender or URL.

## Verification
No further delivery from the sender and no rule forwarding to external addresses.
