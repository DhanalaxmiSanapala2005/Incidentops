---
doc_id: soc_quantum_harvest_now_decrypt_later
version: 1
category: security
access: engineer
recommended_action: none
---
# Quantum 'Harvest Now, Decrypt Later'

## Alert names
Quantum 'Harvest Now, Decrypt Later'

## Symptoms
This alert fires when encrypted traffic is captured by a source with characteristics suggesting long-term storage rather than real-time interception — consistent with an adversary intending to decrypt the data later once quantum computing makes today's encryption breakable. The investigation focuses less on immediate compromise and more on how sensitive the captured data is over the long term.

## Diagnosis
1. Source characterization Identify whether the capturing source shows high-value or nation-state-pattern characteristics rather than routine network noise.
2. Data sensitivity horizon Assess what kind of data was in the captured traffic and how long it needs to remain confidential — data that's only sensitive for weeks is a very different concern than data that must stay protected for years or decades.
3. Current cryptographic exposure Check what encryption algorithms were in use for the captured traffic and whether they're already known to be quantum-vulnerable.
4. Migration readiness Check whether a post-quantum migration plan and cryptographic asset inventory already exist, or whether this is the first prompt to start one.
5. Response This isn't a contain-and-close case in the traditional sense — begin crypto-agility planning, inventory cryptographic assets across the environment, and prioritize migrating long-term-sensitive data to post-quantum algorithms rather than expecting a single remediation step to close it.

## Remediation
Suspend the user's access to the data source and notify the data owner (simulated). Requires engineer approval. Synthetic addition, not from the source playbook.

## Side effects
User cannot work with the affected data until access is restored.

## Rollback plan
Restore access after the owner confirms the activity was legitimate.

## Verification
No further bulk reads or exports and owner sign-off recorded.
