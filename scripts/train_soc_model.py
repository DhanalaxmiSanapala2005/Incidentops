"""Trains a small, interpretable logistic-regression triage model on the labelled synthetic SOC file and
EXPORTS plain coefficients (no sklearn needed at runtime). Reports held-out metrics; nothing is hand-edited.
Usage: python scripts/train_soc_model.py path/to/synthetic_train.xlsx   (needs scikit-learn, pandas, openpyxl)"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
ROOT = Path(__file__).resolve().parents[1]
df = pd.read_excel(sys.argv[1], sheet_name="Alerts")
CAT = ["title", "user_role", "sandbox_verdict", "file_hash_reputation", "severity"]
cols = df.columns[df.columns.get_loc("user_role") + 1: df.columns.get_loc("sandbox_verdict")].tolist()
BOOL = [c for c in cols if set(df[c].dropna().unique()) <= {0, 1}]; NUM = [c for c in cols if c not in BOOL]
stats = {c: (float(df[c].mean()), float(df[c].std() or 1)) for c in NUM}
def feats(r):
    f = {}
    for c in BOOL:
        if pd.notna(r[c]): f[f"{c}={int(r[c])}"] = 1.0
    for c in NUM:
        if pd.notna(r[c]): f[c] = (float(r[c]) - stats[c][0]) / stats[c][1]
    for c in CAT:
        if pd.notna(r[c]): f[f"{c}={r[c]}"] = 1.0
    return f
F = [feats(r) for _, r in df.iterrows()]; names = sorted({k for f in F for k in f})
X = np.array([[f.get(n, 0.0) for n in names] for f in F]); y = df["is_true_positive"].astype(int).values
Xtr, Xte, ytr, yte, dtr, dte = train_test_split(X, y, df, test_size=0.3, random_state=42, stratify=y)
lr = LogisticRegression(C=0.5, max_iter=3000).fit(Xtr, ytr); p = lr.predict_proba(Xte)[:, 1]; pred = (p >= 0.5).astype(int)
base = (dte["severity"] == "High").astype(int).values
met = lambda yp, ps=None: {"precision": round(precision_score(yte, yp), 3), "recall": round(recall_score(yte, yp), 3), "f1": round(f1_score(yte, yp), 3),
                           **({"roc_auc": round(roc_auc_score(yte, ps), 3)} if ps is not None else {})}
res = {"n_total": len(df), "n_train": len(ytr), "n_test": len(yte), "test_tp_rate": round(float(yte.mean()), 3),
       "baseline_severity_high_is_tp": met(base), "logistic_regression": met(pred, p)}
coef = dict(zip(names, map(float, lr.coef_[0])))
(ROOT / "data/soc_model.json").write_text(json.dumps({"bools": BOOL, "numeric": NUM, "numeric_stats": stats, "categorical": CAT, "intercept": float(lr.intercept_[0]),
                                                    "coef": coef, "metrics": res, "trained_on": "synthetic_train.xlsx (synthetic labels; stratified 70/30 split, seed 42)"}, indent=1), encoding="utf-8")
top = sorted(coef.items(), key=lambda kv: -abs(kv[1]))[:12]
(ROOT / "docs/soc_eval.md").write_text("# SOC triage model: measured results\n\nData: synthetic labelled alerts (n=%d); stratified 70/30 split, seed 42, test n=%d (true-positive rate %.1f%%).\n"
  "Baseline = severity-only rule (predict true positive if severity is High). Model = logistic regression on playbook-derived features, threshold 0.5.\n\n"
  "| Method | Precision | Recall | F1 | ROC AUC |\n|---|---|---|---|---|\n| Severity-only baseline | %s | %s | %s | n/a |\n| Logistic regression | %s | %s | %s | %s |\n\n"
  "Strongest features: %s\n\nCaveat: labels and features are SYNTHETIC. Results show the pipeline works, not real-world accuracy. Re-run with analyst-labelled alerts before relying on it.\n"
  % (len(df), len(yte), 100 * yte.mean(), *[res["baseline_severity_high_is_tp"][k] for k in ("precision", "recall", "f1")], *[res["logistic_regression"][k] for k in ("precision", "recall", "f1", "roc_auc")],
     ", ".join(f"{k} ({v:+.2f})" for k, v in top)), encoding="utf-8")
print(json.dumps(res, indent=1))
