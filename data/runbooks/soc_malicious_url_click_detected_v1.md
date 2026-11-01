---
doc_id: soc_malicious_url_click_detected
version: 1
category: security
access: engineer
recommended_action: none
---
# Malicious URL Click Detected

## Alert names
Malicious URL Click Detected; A potentially malicious URL click was detected

## Symptoms
This alert fires when a user clicks a link in an email that has been identified as malicious, either at the time of delivery or after the fact. The investigation needs to establish whether the link and its message were genuinely malicious, whether the click led to any further compromise, and whether the user needs to be notified.

## Diagnosis
1. ZAP → Quarantine Check whether the message was automatically pulled back or quarantined after delivery (Zero-Hour Auto Purge) and compare that timing against when the user actually clicked. If the message was removed before the click, the user likely never reached the live page.
2. User information & ID history Look at the recipient's recent email history to see if they've interacted with flagged senders before. A user with a pattern of engaging with suspicious mail is a higher priority case, independent of how this particular click turns out.
3. Email authentications: DMARC, SPF, DKIM Check whether the message passed or failed standard email authentication checks. A hard fail across the board combined with a spoofed display name is a strong sign of malicious intent, while a clean pass from a known partner domain supports a benign read.
4. Sender path & return path Compare the visible “From” address against the actual return path the message was sent through. A mismatch between the two is a classic spoofing technique used to make a malicious email look like it came from someone trustworthy.
5. Sender info Look at how established the sender is — how long they've been emailing the organization and how many other people they've contacted. A first-time sender with very low volume or a newly registered domain is far more suspicious than an established contact.
6. Mail's attachments / URLs Review any attachments or additional links included in the same message. Multiple redirects, shortened links, or a chain that ultimately leads to a credential-harvesting page are all strong indicators of malicious intent.
7. URL's sandbox Check the detonation/sandbox result for the specific URL that was clicked. This tells you definitively whether the link leads to a malicious page and whether it was actually blocked before the user reached it or whether they got through to the live content.
8. User Office 365 audit logs — to check whether the account is compromised or not Review the user's account activity in the hour or so after the click for signs of compromise — a new inbox rule, a mailbox permission change, or a sign-in from an unfamiliar location. Any of these means the account should be treated as compromised regardless of how the URL itself is classified.
9. Sender history Check whether this sender or their domain has been flagged in previous incidents against the organization. A domain with a track record of malicious mail should be blocked outright rather than evaluated message by message.
10. If not malicious, no need to send mail If every check above comes back clean, close the alert without notifying the user — there's no need to send a follow-up email or alert them to a false alarm.

## Remediation
Purge the message from mailboxes, block the sender or URL and remove malicious mailbox rules (simulated). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
Legitimate mail from the same sender may be delayed or blocked.

## Rollback plan
Release the quarantined message and unblock the sender or URL.

## Verification
No further delivery from the sender and no rule forwarding to external addresses.
