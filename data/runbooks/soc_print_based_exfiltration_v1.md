---
doc_id: soc_print_based_exfiltration
version: 1
category: security
access: engineer
recommended_action: none
---
# Print-Based Exfiltration

## Alert names
Print-Based Exfiltration

## Symptoms
This alert fires when sensitive documents are printed in a pattern consistent with physical removal rather than normal business use. The investigation focuses on whether the printing reflects a real intent to exfiltrate data physically, since this bypasses most network-based DLP controls entirely.

## Diagnosis
1. Volume and content Check for a print-volume spike tied to one user, and identify exactly what was printed and whether it contains sensitive information.
2. Timing Note when the printing occurred — after-hours printing is a stronger signal than the same activity during a normal workday.
3. User context Check whether the user is departing the organization or already under investigation for something else, which meaningfully raises the priority of the case.
4. Pattern over time Look at whether this is a one-off spike or a frequency that's been increasing, which points more toward a deliberate pattern than a coincidence.
5. Response Loop in HR/Legal given the physical and personnel nature of this alert, and restrict print access if the pattern and intent both point toward genuine exfiltration.

## Remediation
Suspend the user's access to the data source and notify the data owner (simulated). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
User cannot work with the affected data until access is restored.

## Rollback plan
Restore access after the owner confirms the activity was legitimate.

## Verification
No further bulk reads or exports and owner sign-off recorded.
