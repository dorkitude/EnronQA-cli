"""Pull representative reviewed items per category/verdict for the report (local output; contains dataset text).

Writes work/examples.md. Only a hand-selected, short subset should be copied into the public report.
"""
import polars as pl, sys, json
sys.path.insert(0, "scripts"); from common import questions, LEDGER, WORK
sem = pl.read_parquet(LEDGER / "semantic.parquet")
q = questions().select("qid", "question", "gold")
j = sem.join(q, on="qid")
out = []
for (cat, verdict), g in sorted(j.group_by("cat", "verdict"), key=lambda kv: (-len(kv[1]), kv[0])):
    out.append(f"\n## {cat} / {verdict}  (n={g.height})\n")
    for r in g.sort("conf").head(4).iter_rows(named=True):
        out.append(f"- `{r['qid']}` conf={r['conf']} flags={r['flags']}\n  - Q: {r['question']}\n  - gold: {r['gold']}\n  - canon: {r['canon']}" + (f"\n  - aliases: {r['aliases']}" if r['aliases'] else "") + (f"\n  - rewritten question: {r['rq']}" if r['rq'] else "") + (f"\n  - note: {r['note']}" if r['note'] else ""))
(WORK / "examples.md").write_text("\n".join(out))
print("wrote", WORK / "examples.md", "groups:", j.group_by("cat", "verdict").len().height)
