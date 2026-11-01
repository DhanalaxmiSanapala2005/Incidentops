---
doc_id: soc_click_jacking_ui_redress
version: 1
category: security
access: engineer
recommended_action: none
---
# Click-Jacking / UI Redress

## Alert names
Click-Jacking / UI Redress

## Symptoms
This alert fires when an attacker embeds a site in a hidden or transparent iframe on their own page, tricking users into clicking on something they didn't intend to interact with. The investigation focuses on whether a sensitive action was actually exploited this way, not just whether the technique was attempted.

## Diagnosis
1. Embedding confirmation Check whether the site is actually being framed on an attacker-controlled page, and confirm whether X-Frame-Options or a CSP frame-ancestors policy is missing.
2. Exploitable action Identify whether the framed page exposes a sensitive action — a funds transfer or account deletion button is a serious finding, while a framed static content page is largely cosmetic.
3. User impact Check whether any users actually triggered the unintended action, and how many.
4. Pattern over time Determine whether this is an isolated finding (e.g., from a pen test) or an active, ongoing abuse pattern.
5. Containment Add X-Frame-Options: DENY or the equivalent CSP frame-ancestors directive, audit any actions that were triggered through the framed page, and notify affected users if real impact occurred.

## Remediation
Apply a WAF rule or block the abusive source and ask the application owner to patch (simulated). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
Possible false blocks of legitimate traffic from the same range.

## Rollback plan
Remove the WAF rule or block entry.

## Verification
No repeat requests matching the pattern after the rule is applied.
