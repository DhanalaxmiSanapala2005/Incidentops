# RAG retrieval evaluation (measured, synthetic data)

Test set: `data/pack/evaluation/rag_eval_queries.json` (41 queries; 35 with an expected runbook, 34 with an expected past incident). Runbook hit = any expected runbook within the top K documents. Leakage = admin-only documents returned to a lower role in the top 5 (must be 0). Last column: if the lowest best-score of real questions is above the highest best-score of out-of-scope questions, a score cutoff could refuse out-of-scope questions; set RAG_MIN_DENSE only after checking this on your own data.

| Method | Runbook @1 | Runbook @3 | Runbook @5 | MRR | Past incident @3 | Leakage | Current version first | Top score |
|---|---|---|---|---|---|---|---|---|
| Keyword only (TF-IDF) | 24/35 (69%) | 32/35 (91%) | 33/35 (94%) | 0.80 | 29/34 | 0 | 2/2 | lowest in-scope 1.00, highest out-of-scope 0.96 |

Hybrid not run: EMBED_PROVIDER is not 'ollama'. Set it and start Ollama (see README), then run this script again.

Limits: 41 questions written by the project author on synthetic documents; one run.
