"""SOC alert triage. Pure-python scoring with exported logistic-regression coefficients (see scripts/train_soc_model.py).
The score is a STATISTICAL ESTIMATE from synthetic training data, never a confirmed verdict; with too few signals we say so."""
import json, math
from backend.config import ROOT
try: MODEL = json.loads((ROOT / "data" / "soc_model.json").read_text(encoding="utf-8"))
except FileNotFoundError: MODEL = None
FEATURE_COLS = (MODEL["bools"] + MODEL["numeric"] + [c for c in MODEL["categorical"] if c not in ("title", "severity")]) if MODEL else []
MIN_SIGNALS = 3


def vectorize(f: dict) -> dict:
    out = {}
    for c in MODEL["bools"]:
        if f.get(c) is not None: out[f"{c}={int(f[c])}"] = 1.0
    for c, (mu, sd) in MODEL["numeric_stats"].items():
        if f.get(c) is not None: out[c] = (float(f[c]) - mu) / sd
    for c in MODEL["categorical"]:
        if f.get(c) is not None: out[f"{c}={f[c]}"] = 1.0
    return out


def signal_count(f: dict) -> int:
    return sum(1 for c in MODEL["bools"] + MODEL["numeric"] if f.get(c) is not None) if MODEL else 0


def score(f: dict):
    v = vectorize(f); contrib = {k: MODEL["coef"].get(k, 0.0) * x for k, x in v.items()}
    z = MODEL["intercept"] + sum(contrib.values())
    return 1 / (1 + math.exp(-z)), sorted(contrib.items(), key=lambda kv: -abs(kv[1]))


def detect(f: dict, evidence: list[dict]) -> list[dict]:
    """Returns hypotheses in the same shape the rest of the workflow expects (op=None: analysts act, nothing auto-executes)."""
    title = f.get("title", "alert")
    alert_ev = [e["id"] for e in evidence if e["type"] == "alert"]; ind_ev = [e["id"] for e in evidence if e["type"] in ("indicator", "identity")]
    h = {"id": "H1", "op": None, "params": None}
    if not MODEL or signal_count(f) < MIN_SIGNALS:
        return [{**h, "signal": "insufficient_evidence", "title": f"{title}: not enough investigation data for a verdict", "confidence": 0.3, "uncertain": True,
                 "evidence_ids": alert_ev, "explanation": "Only base SIEM fields were available (no sign-in history, IP reputation, sandbox verdict or user context). "
                 "No verdict is given. Work through the retrieved playbook steps and attach the results to this incident."}]
    p, contrib = score(f); top = ", ".join(f"{k} ({v:+.2f})" for k, v in contrib[:3])
    if p >= 0.7: sig, label, conf = "likely_true_positive", "Likely true positive", p
    elif p <= 0.3: sig, label, conf = "likely_false_positive", "Likely false positive", 1 - p
    else: sig, label, conf = "inconclusive", "Inconclusive", max(p, 1 - p)
    ev = ind_ev or alert_ev
    return [{**h, "signal": sig, "title": f"{label}: {title}", "confidence": round(conf, 2), "uncertain": sig == "inconclusive" or len(ev) < 2, "evidence_ids": ev,
             "explanation": f"Model estimate of {p:.0%} true-positive likelihood. Largest contributors: {top}. This is a statistical estimate from synthetic training data, "
                            "not a confirmed root cause; an analyst must confirm using the playbook. Containment is not automated for security alerts."}]
