# SOC triage model: measured results

Data: synthetic labelled alerts (n=6000); stratified 70/30 split, seed 42, test n=1800 (true-positive rate 42.7%).
Baseline = severity-only rule (predict true positive if severity is High). Model = logistic regression on playbook-derived features, threshold 0.5.

| Method | Precision | Recall | F1 | ROC AUC |
|---|---|---|---|---|
| Severity-only baseline | 0.527 | 0.698 | 0.601 | n/a |
| Logistic regression | 0.809 | 0.731 | 0.768 | 0.875 |

Strongest features: post_activity_suspicious=1 (+1.24), recipients_count (+1.14), activity_volume_zscore (+0.98), exploit_confirmed=1 (+0.94), ip_reputation_score (+0.93), campaign_linked=1 (+0.88), forwarding_deletes_original=1 (+0.83), sender_first_time=1 (+0.82), file_hash_reputation=known_bad (+0.77), user_travels_for_work=1 (-0.77), c2_traffic_observed=1 (+0.76), broad_permissions=0 (-0.74)

Caveat: labels and features are SYNTHETIC. Results show the pipeline works, not real-world accuracy. Re-run with analyst-labelled alerts before relying on it.
