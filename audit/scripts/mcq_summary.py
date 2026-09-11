"""Programmatic checks on the supplied incorrect_answers (MCQ distractor quality), 100% coverage."""
import polars as pl, json, re, sys
sys.path.insert(0, "scripts"); from common import questions, REPORT
q = questions().select("qid", "split", "gold", "alternates", "incorrects")
def norm(s): return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", (s or "").lower())).strip()
rows = []
for qid, split, gold, alts, incs in q.iter_rows():
    g = norm(gold); a = norm(alts[0]); i1, i2 = norm(incs[0]), norm(incs[1])
    rows.append({"split": split, "inc_identical_pair": i1 == i2, "inc_equals_gold_or_alt": i1 in (g, a) or i2 in (g, a),
                 "inc_empty": not i1 or not i2, "gold_equals_alt": g == a,
                 "inc_starts_generic": any(x.startswith(("the email does not", "there is no", "it is not", "we cannot", "the answer is not")) for x in (i1, i2))})
df = pl.DataFrame(rows)
out = {}
for c in ["inc_identical_pair", "inc_equals_gold_or_alt", "inc_empty", "gold_equals_alt", "inc_starts_generic"]:
    out[c] = {s: {"n": int(df.filter(pl.col("split") == s)[c].sum()), "pct": round(100 * df.filter(pl.col("split") == s)[c].mean(), 2)} for s in ["train", "dev", "test"]}
    out[c]["all_n"] = int(df[c].sum())
json.dump(out, open(REPORT / "mcq_summary.json", "w"), indent=1)
print(json.dumps(out, indent=1))
