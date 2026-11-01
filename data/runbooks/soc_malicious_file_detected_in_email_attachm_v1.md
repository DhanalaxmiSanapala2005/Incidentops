---
doc_id: soc_malicious_file_detected_in_email_attachm
version: 1
category: security
access: engineer
recommended_action: none
---
# Malicious File Detected in Email Attachment

## Alert names
Malicious File Detected in Email Attachment

## Symptoms
This alert fires when an attachment in an email is flagged as malicious, either through signature matching or sandbox detonation. The investigation follows the same overall pattern as a malicious URL click, but focuses on the file itself — confirming it's genuinely dangerous, checking whether it reached or was opened by the recipient, and understanding how far it may have spread.

## Diagnosis
1. ZAP → Quarantine Check whether the message carrying the attachment was pulled back or quarantined tenant-wide before the recipient had a chance to open it.
2. User information & ID history Check whether this recipient regularly receives similar attachments as part of their normal role — for example, someone in Finance who routinely gets invoice templates — before treating the detection as unusual.
3. Email authentications: DMARC, SPF, DKIM Check the message's authentication results. Failures alongside a malicious attachment verdict increase confidence this is a targeted or spoofed delivery rather than an error from a legitimate partner.
4. Sender path & return path Compare the visible sender address against the actual return path. A mismatch on a message carrying a malicious file is a strong indicator of a deliberate phishing attempt.
5. Sender info Check how established the sender is with the organization. A long-standing partner with a single flagged message is a stronger false-positive candidate than a sender no one has heard from before.
6. Mail's attachments / URLs Review the attachment's file type, hash, and any links embedded inside it or in the surrounding message, to build a full picture of what the file is and what it does.
7. URL's sandbox Check the sandbox detonation result for the attachment itself. A behavioral verdict — for example, a macro that drops a second-stage payload or reaches out to a command-and-control server — is high confidence malicious, while a static signature-only match on an otherwise normal template is worth a closer manual look.
8. User Office 365 audit logs — to check whether the account is compromised or not Check whether the recipient actually opened or ran the attachment. Evidence that they did means this is no longer just an email alert — it needs to be escalated to check the endpoint itself.
9. Sender history Check whether this sender or domain has a track record of sending flagged messages before. Repeat offenders should be blocked outright rather than handled case by case.
10. If not malicious, no need to send mail If everything checks out clean, release the message from quarantine and close the alert — there's no need to notify the user or take further action.

## Remediation
Isolate the endpoint from the network and run a full scan (simulated; not yet automated in the sandbox). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
User loses network access to the device until released.

## Rollback plan
Release the device from isolation once the scan is clean.

## Verification
Scan clean, no outbound connections to flagged hosts, file hash confirmed quarantined.
