---
doc_id: soc_calendar_meeting_invite_phishing
version: 1
category: security
access: engineer
recommended_action: none
---
# Calendar / Meeting Invite Phishing

## Alert names
Calendar / Meeting Invite Phishing

## Symptoms
This alert fires when a phishing attempt arrives as a calendar invite rather than an email — a format that in some mail clients gets auto-accepted, giving the malicious link or join URL more visibility than a normal phishing email would get. The investigation focuses on whether the invite was interacted with and how it entered the user's calendar in the first place.

## Diagnosis
1. Sender and invite legitimacy Check whether the invite came from an unknown or unexpected sender, and inspect the join URL or attachment for anything suspicious.
2. Auto-accept exposure Check whether the invite was auto-accepted by the user's calendar settings, since that changes how much visibility the malicious content already had.
3. Interaction Determine whether the user actually clicked the join URL, and if so, whether it led to a credential harvest page or a malware delivery attempt.
4. Source pattern Check whether the sending account is spoofed or genuinely compromised, and whether multiple users received a similar invite.
5. Response Block the sender and the URL, disable calendar auto-accept by policy going forward, and brief users on the pattern if it looks like a broader campaign rather than an isolated attempt.

## Remediation
Purge the message from mailboxes, block the sender or URL and remove malicious mailbox rules (simulated). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
Legitimate mail from the same sender may be delayed or blocked.

## Rollback plan
Release the quarantined message and unblock the sender or URL.

## Verification
No further delivery from the sender and no rule forwarding to external addresses.
