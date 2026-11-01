"""SOC evaluation against a RUNNING stack: playbook retrieval Recall@1/@3, grounded-hypothesis coverage, insufficient-evidence rate,
and the safety invariant that security alerts never create executable actions. Appends a section to docs/evaluation_report.md."""
import os, re, sys, requests
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; API = os.getenv("API_URL", "http://localhost:8000")
tok = lambda u, p: {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"username": u, "password": p}).json()["access_token"]}
adm, eng = tok("admin", "admin123"), tok("engineer", "engineer123")
requests.post(f"{API}/admin/reset", headers=adm)
names = {}
for f in (ROOT / "data/runbooks").glob("soc_*.md"):
    t = f.read_text(encoding="utf-8"); doc = re.search(r"doc_id: (\S+)", t).group(1)
    for n in re.search(r"## Alert names\n(.+)", t).group(1).split(";"): names[n.strip().lower()] = doc
ids = []
for sample, lim in (("soc_real", 17), ("soc_labelled", 51)):
    ids += requests.post(f"{API}/import/sample/{sample}", params={"limit": lim}, headers=eng).json()["incident_ids"]
n = r1 = r3 = grounded = hyps = insuff = 0; unmapped = set(); sig = {}
for i in ids:
    requests.post(f"{API}/incidents/{i}/investigate", headers=eng)
    d = requests.get(f"{API}/incidents/{i}", headers=eng).json(); inv = d["investigation"]; want = names.get(d["title"].lower())
    if not want: unmapped.add(d["title"]); continue
    docs = []
    for r in inv["runbooks"]:
        if r["doc_id"] not in docs: docs.append(r["doc_id"])
    n += 1; r1 += bool(docs[:1] == [want]); r3 += want in docs[:3]
    for h in inv["hypotheses"]:
        hyps += 1; grounded += bool(h["evidence_ids"]); sig[h["signal"]] = sig.get(h["signal"], 0) + 1
    insuff += inv["hypotheses"][0]["signal"] == "insufficient_evidence"
actions = len(requests.get(f"{API}/actions", headers=eng).json())
sec = (f"\n## SOC alerts (measured)\n\n- Test set: {len(ids)} imported security incidents ({n} mapped to a playbook; 17 alert types; unmapped titles: {sorted(unmapped) or 'none'})\n"
       f"- Playbook retrieval Recall@1: **{r1}/{n} = {r1 / n:.1%}**, Recall@3: **{r3}/{n} = {r3 / n:.1%}** (TF-IDF over runbooks and resolved incidents)\n"
       f"- Grounded hypotheses (cite at least one evidence id): **{grounded}/{hyps}**\n- Hypothesis mix: {sig}; insufficient-evidence rate {insuff / n:.1%}\n"
       f"- Executable actions created for security alerts: **{actions}** (expected 0: investigation-only by design)\n"
       "- Triage model quality on a held-out split: see `docs/soc_eval.md` (synthetic data).\n")
rep = ROOT / "docs/evaluation_report.md"; t = rep.read_text(encoding="utf-8"); t = re.split(r"\n## SOC alerts", t)[0].rstrip() + "\n" + sec
rep.write_text(t, encoding="utf-8"); print(sec)
