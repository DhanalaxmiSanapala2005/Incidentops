---
doc_id: soc_open_redirect
version: 1
category: security
access: engineer
recommended_action: none
---
# Open Redirect

## Alert names
Open Redirect

## Symptoms
This alert fires when a redirect parameter on a trusted site can be manipulated to send users to an attacker-controlled URL, often used to add legitimacy to a phishing campaign. The investigation focuses on confirming the parameter is genuinely exploitable and understanding how it's being used.

## Diagnosis
1. Parameter check Confirm whether the redirect parameter accepts arbitrary external URLs rather than being restricted to an allow-list.
2. Abuse pattern Check whether the redirect is being chained with something more serious, such as an OAuth flow, to steal trust rather than just redirect traffic.
3. User reports and volume Look at how many users were actually redirected through the site, and whether any reported landing on a phishing page after clicking what looked like a legitimate link.
4. Campaign context Check whether this redirect is part of an active phishing campaign abusing the domain's reputation.
5. Containment Patch the redirect logic with a destination allow-list, tighten the WAF, and notify affected users if the exposure was significant.

## Remediation
Apply a WAF rule or block the abusive source and ask the application owner to patch (simulated). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
Possible false blocks of legitimate traffic from the same range.

## Rollback plan
Remove the WAF rule or block entry.

## Verification
No repeat requests matching the pattern after the rule is applied.
