"""Rewrite the auto-generated blocks in report/REPORT.md from aggregates.json and agreement.json.

Blocks are delimited by <!-- AUTO:name --> ... <!-- /AUTO:name -->. Everything else in REPORT.md is hand-written.
"""
import json, re, sys, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import REPORT

agg = json.load(open(REPORT / "aggregates.json"))
rep = (REPORT / "REPORT.md").read_text()

def pct(n, d): return f"{100*n/d:.1f}%" if d else "n/a"

sem = agg.get("semantic")
if sem:
    n = sem["reviewed_questions"]; tot = agg["total_questions"]; ps = agg["per_split"]; cov = sem["reviewed_per_split"]
    v = sem["verdict_counts"]; c = sem["cat_counts"]; f = sem["flag_counts"]
    conv = v.get("convertible", 0); rew = v.get("convertible_rewrite", 0); unc = v.get("unconvertible", 0)
    topcats = ", ".join(f"`{k}` {pct(val, n)}" for k, val in sorted(c.items(), key=lambda kv: -kv[1])[:8])
    coverage = f"""**Reviewed so far: {n:,} of {tot:,} questions ({pct(n, tot)})** from {sem['reviewed_emails']:,} of 73,772 emails
(train {cov['train']:,}/{ps['train']:,} = {pct(cov['train'], ps['train'])}; dev {cov['dev']:,}/{ps['dev']:,} = {pct(cov['dev'], ps['dev'])}; test {cov['test']:,}/{ps['test']:,} = {pct(cov['test'], ps['test'])}).
Generated {datetime.datetime.now(datetime.UTC):%Y-%m-%d %H:%M} UTC from `aggregates.json`. The remaining {tot - n:,} questions have **not** been semantically reviewed; the percentages below describe the reviewed set only.

| Verdict | n | share of reviewed |
|---|---|---|
| convertible (as asked) | {conv:,} | {pct(conv, n)} |
| convertible after question rewrite | {rew:,} | {pct(rew, n)} |
| unconvertible (needs judge or task change) | {unc:,} | {pct(unc, n)} |

Most frequent schema categories: {topcats}.
Rewrites that narrow the original information need (drop a sub-question): {sem.get("narrowed",{}).get("narrowed_true",0):,} of {rew:,} rewrite items ({sem.get("narrowed",{}).get("narrowed_unknown_old_prompt",0):,} reviewed before the marker existed).
Most frequent flags: {", ".join(f"`{k}` {pct(val, n)}" for k, val in sorted(f.items(), key=lambda kv: -kv[1])[:6])}."""
else:
    coverage = "No semantic review collected yet."
rep = re.sub(r"<!-- AUTO:coverage -->.*?<!-- /AUTO:coverage -->", f"<!-- AUTO:coverage -->\n{coverage}\n<!-- /AUTO:coverage -->", rep, flags=re.S)

agr_path = REPORT / "agreement.json"
if agr_path.exists():
    a = json.load(open(agr_path))
    byconf = a.get("verdict_agreement_by_conf_a", {})
    agr = f"""Second pass at effort `medium` over {a['paired_items']:,} already-reviewed items (same model, independent call):

| Measure | agreement |
|---|---|
| schema category identical | {100*a['cat_agreement']:.1f}% |
| verdict identical (3-way) | {100*a['verdict_agreement']:.1f}% |
| convertible-vs-unconvertible identical | {100*a['convertible_vs_unconvertible_agreement']:.1f}% |
| canonical answer byte-identical (case-folded) | {100*a['canon_exact_agreement']:.1f}% |

Verdict agreement by first-pass confidence: {", ".join(f"{k}: {100*vv['agree']:.0f}% (n={vv['n']})" for k, vv in byconf.items())}.
This measures self-consistency of the Fable labels, not agreement with humans. Canonical answers vary in surface form far more than categories do, which is itself evidence that per-item normalization rules and alias lists are required before deterministic scoring."""
else:
    agr = "Second pass not yet run."
rep = re.sub(r"<!-- AUTO:agreement -->.*?<!-- /AUTO:agreement -->", f"<!-- AUTO:agreement -->\n{agr}\n<!-- /AUTO:agreement -->", rep, flags=re.S)
(REPORT / "REPORT.md").write_text(rep)
print("REPORT.md updated")
