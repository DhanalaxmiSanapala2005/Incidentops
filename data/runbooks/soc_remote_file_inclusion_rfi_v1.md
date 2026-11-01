---
doc_id: soc_remote_file_inclusion_rfi
version: 1
category: security
access: engineer
recommended_action: none
---
# Remote File Inclusion (RFI)

## Alert names
Remote File Inclusion (RFI)

## Symptoms
This alert fires when a web application is manipulated into loading and executing a remote file through a vulnerable include parameter, potentially handing an attacker remote code execution. The investigation focuses on confirming exploitation, checking for a dropped web shell, and determining whether the application needs to be patched or rebuilt.

## Diagnosis
1. Trigger confirmation Check the WAF alert for the malicious URL passed into the include parameter, and confirm whether the app tier made an outbound call to an external host as a result.
2. Execution outcome Determine whether the remote file actually executed — look for a web shell or other remote code running as a result.
3. Persistence check Look for signs the attacker established persistence after the initial execution, not just a one-time hit.
4. Source and scope Check the source IP for signs of broader endpoint enumeration against the same application.
5. Containment Patch the vulnerable include (disable allow_url_include or the framework equivalent), restrict egress from the app tier, and reimage the host if remote code execution is confirmed rather than just attempted.

## Remediation
Apply a WAF rule or block the abusive source and ask the application owner to patch (simulated). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
Possible false blocks of legitimate traffic from the same range.

## Rollback plan
Remove the WAF rule or block entry.

## Verification
No repeat requests matching the pattern after the rule is applied.
