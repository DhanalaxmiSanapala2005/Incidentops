---
doc_id: soc_dns_subdomain_enumeration
version: 1
category: security
access: engineer
recommended_action: none
---
# DNS / Subdomain Enumeration

## Alert names
DNS / Subdomain Enumeration

## Symptoms
This alert fires when DNS query patterns suggest an attacker is systematically enumerating subdomains, typically searching for forgotten or weakly secured assets that were never meant to be found. The investigation focuses on identifying what was probed and whether any of it represents a real exposure.

## Diagnosis
1. Query pattern Check whether the DNS queries show a brute-force enumeration pattern rather than normal resolution traffic, and whether known tooling signatures (Sublist3r, Amass) are present.
2. Certificate transparency correlation Cross-check certificate transparency logs for the same reconnaissance pattern, since CT logs are a common companion source attackers use alongside direct DNS enumeration.
3. Target assessment Determine whether any of the enumerated subdomains are genuinely forgotten, unmaintained, or running outdated software.
4. Takeover risk Check specifically for subdomain takeover exposure — a subdomain pointing to a deprovisioned cloud resource is a much more urgent finding than a simple inventory gap.
5. Response Inventory every subdomain found in the probe, decommission anything unused, and put continuous monitoring in place for the domain going forward rather than treating this as a one-time cleanup.

## Remediation
Apply a WAF rule or block the abusive source and ask the application owner to patch (simulated). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
Possible false blocks of legitimate traffic from the same range.

## Rollback plan
Remove the WAF rule or block entry.

## Verification
No repeat requests matching the pattern after the rule is applied.
