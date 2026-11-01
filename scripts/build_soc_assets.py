"""Builds SOC runbooks (from the analyst playbook .docx), a synthetic resolved-incident KB and CSV templates.
Usage: python scripts/build_soc_assets.py [path/to/SOC_Alert_Playbook.docx]"""
import csv, json, re, sys
from datetime import datetime, timedelta
from pathlib import Path
import docx
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/samples/SOC_Alert_Playbook.docx"
# Response classes: SYNTHETIC additions (the analyst playbook has investigation steps only). Actions are simulated and need approval.
CLASSES = {
 "identity": (["impossible travel", "service account", "credential phishing"],
   "Revoke active sessions and force MFA re-registration for the affected account (simulated; not yet automated in the sandbox).",
   "User is signed out of all devices and must sign in again.", "Re-enable the account sessions; no data is deleted.",
   "No new sign-ins from the flagged IP and no new mailbox rules or MFA changes for 24 hours."),
 "endpoint": (["malware", "malicious file"],
   "Isolate the endpoint from the network and run a full scan (simulated; not yet automated in the sandbox).",
   "User loses network access to the device until released.", "Release the device from isolation once the scan is clean.",
   "Scan clean, no outbound connections to flagged hosts, file hash confirmed quarantined."),
 "email": (["forwarding", "spoofing", "calendar", "url click"],
   "Purge the message from mailboxes, block the sender or URL and remove malicious mailbox rules (simulated).",
   "Legitimate mail from the same sender may be delayed or blocked.", "Release the quarantined message and unblock the sender or URL.",
   "No further delivery from the sender and no rule forwarding to external addresses."),
 "web": (["rfi", "open redirect", "click-jacking", "dns"],
   "Apply a WAF rule or block the abusive source and ask the application owner to patch (simulated).",
   "Possible false blocks of legitimate traffic from the same range.", "Remove the WAF rule or block entry.",
   "No repeat requests matching the pattern after the rule is applied."),
 "data": (["print", "database mass", "quantum"],
   "Suspend the user's access to the data source and notify the data owner (simulated).",
   "User cannot work with the affected data until access is restored.", "Restore access after the owner confirms the activity was legitimate.",
   "No further bulk reads or exports and owner sign-off recorded."),
}
def cls(title):
    t = title.lower()
    return next((k for k, v in CLASSES.items() if any(w in t for w in v[0])), "email")
ALIASES = {"Malicious URL Click Detected": ["A potentially malicious URL click was detected"]}
slug = lambda t: re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")[:40]
d = docx.Document(src); books, cur = [], None
for p in d.paragraphs:
    tx = p.text.strip()
    if not tx: continue
    if p.style.name == "Heading 1": cur = {"title": tx, "desc": "", "steps": []}; books.append(cur)
    elif cur is None: continue
    elif re.match(r"^\d+\.\s", tx): cur["steps"].append([tx, ""])
    elif cur["steps"]: cur["steps"][-1][1] += (" " if cur["steps"][-1][1] else "") + tx
    else: cur["desc"] += tx + " "
rb = ROOT / "data/runbooks"
for f in rb.glob("soc_*_v1.md"): f.unlink()
kb = [e for e in json.loads((ROOT / "data/resolved_incidents.json").read_text(encoding="utf-8")) if not e["doc_id"].startswith("INC-S")]
for n, b in enumerate(books, 1):
    c = cls(b["title"]); _, act, side, back, ver = CLASSES[c]; doc = f"soc_{slug(b['title'])}"
    names = [b["title"]] + ALIASES.get(b["title"], [])
    md = (f"---\ndoc_id: {doc}\nversion: 1\ncategory: security\naccess: engineer\nrecommended_action: none\n---\n# {b['title']}\n\n"
          f"## Alert names\n{'; '.join(names)}\n\n## Symptoms\n{b['desc'].strip()}\n\n## Diagnosis\n"
          + "\n".join(f"{h} {t}" for h, t in b["steps"]) + f"\n\n## Remediation\n{act} Requires engineer approval. Synthetic addition, not from the source playbook.\n\n"
          f"## Side effects\n{side}\n\n## Rollback plan\n{back}\n\n## Verification\n{ver}\n")
    (rb / f"{doc}_v1.md").write_text(md, encoding="utf-8")
    kb.append({"doc_id": f"INC-S{n:02d}a", "version": 1, "title": f"{b['title']} (synthetic confirmed incident)", "access": "engineer",
               "text": f"Symptoms matched the playbook: {b['desc'].strip()[:160]} Confirmed true positive after checking {b['steps'][0][0][3:] if b['steps'] else 'history'}. Resolution: {act} Outcome: contained. Playbook {doc} v1."})
    kb.append({"doc_id": f"INC-S{n:02d}b", "version": 1, "title": f"{b['title']} (synthetic benign incident)", "access": "engineer",
               "text": f"Same alert fired but the user, device and IP matched known benign activity (for example travel or an approved tool). Closed as false positive after playbook checks. Playbook {doc} v1."})
(ROOT / "data/resolved_incidents.json").write_text(json.dumps(kb, indent=1), encoding="utf-8")
base = datetime(2026, 10, 20, 9, 0)
from data.scenarios import SCENARIOS; from backend.rules import THRESHOLDS, severity_for
rows = []
for i, s in enumerate(SCENARIOS):
    for a in s["alerts"]:
        thr = THRESHOLDS.get(a["metric"], ("", ""))[0]; ts = base + timedelta(hours=3 * i, minutes=-a["minutes_ago"] + 15)
        rows.append([f"{s['id']}-{len(rows) + 1:03d}", ts.isoformat() + "Z", s["service"], a["metric"], severity_for(a["metric"], a["value"]),
                     a["metric"], a["value"], thr, f"scenario:{s['id']}", s["name"], s["id"]])
with open(ROOT / "data/templates/alerts_infra_template.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow("alert_id timestamp service_name alert_type severity metric_name metric_value threshold source_id description incident_id".split()); w.writerows(rows)
(ROOT / "data/templates/alerts_soc_template.csv").write_text(
    "alert_id,timestamp,product,alert_category,title,severity,description,affected_user,affected_device,source_ip,incident_id,mitre_techniques\n"
    "example-001,2026-10-20T09:00:00Z,EXAMPLE_SIEM,Initial Access,Impossible travel activity detected,High,User signed in from two distant locations,user@example.com,laptop-01,203.0.113.5,9001,T1078\n", encoding="utf-8")
print(len(books), "playbooks,", len(kb), "KB entries,", len(rows), "infra template rows")
