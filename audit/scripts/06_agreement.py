"""Label-reliability check: re-review already-reviewed batches with a second pass and
measure agreement on `cat` and `verdict`. Same model, higher effort (default medium), so
this measures self-consistency of the Fable labels, not human agreement.

  uv run scripts/06_agreement.py run --n 20 --workers 3
  uv run scripts/06_agreement.py report
"""
import argparse, json, os, sys
from pathlib import Path
import polars as pl
sys.path.insert(0, str(Path(__file__).parent))
import importlib
os.environ.setdefault("REVIEW_EFFORT", "medium")
m = importlib.import_module("03_semantic_review")
from common import CACHE, REPORT

SECOND = CACHE / "reviews_second"; SECOND.mkdir(exist_ok=True)

def run(n, workers):
    done = sorted(m.REV_DIR.glob("*.json"))[:n]
    m.REV_DIR = SECOND          # write second-pass results elsewhere
    from concurrent.futures import ThreadPoolExecutor
    files = [m.BATCH_DIR / d.name for d in done]
    with ThreadPoolExecutor(workers) as ex:
        for stem, msg in ex.map(m.run_one, files):
            print(stem, msg, flush=True)

def report():
    rows = []
    for s in sorted(SECOND.glob("*.json")):
        f = m.REV_DIR / s.name
        if not f.exists():
            continue
        a = {it["qid"]: it for it in json.loads(f.read_text())["items"]}
        b = {it["qid"]: it for it in json.loads(s.read_text())["items"]}
        for qid in a.keys() & b.keys():
            rows.append({"qid": qid, "cat_a": a[qid].get("cat"), "cat_b": b[qid].get("cat"), "verdict_a": a[qid].get("verdict"), "verdict_b": b[qid].get("verdict"),
                         "conf_a": a[qid].get("conf"), "canon_a": json.dumps(a[qid].get("canon")), "canon_b": json.dumps(b[qid].get("canon"))})
    df = pl.DataFrame(rows)
    if df.height == 0:
        print("no paired items"); return
    def agree(c1, c2): return float((df[c1] == df[c2]).mean())
    conv = lambda c: df[c].is_in(["convertible", "convertible_rewrite"])
    out = {"paired_items": df.height,
           "cat_agreement": agree("cat_a", "cat_b"), "verdict_agreement": agree("verdict_a", "verdict_b"),
           "convertible_vs_unconvertible_agreement": float((conv("verdict_a") == conv("verdict_b")).mean()),
           "canon_exact_agreement": float((df["canon_a"].str.to_lowercase() == df["canon_b"].str.to_lowercase()).mean()),
           "verdict_agreement_by_conf_a": {r["conf_a"]: {"n": r["n"], "agree": r["agree"]} for r in df.group_by("conf_a").agg(pl.len().alias("n"), (pl.col("verdict_a") == pl.col("verdict_b")).mean().alias("agree")).to_dicts()},
           "confusion_verdict": df.group_by("verdict_a", "verdict_b").len().sort("len", descending=True).to_dicts()}
    json.dump(out, open(REPORT / "agreement.json", "w"), indent=1)
    print(json.dumps(out, indent=1))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--n", type=int, default=20); r.add_argument("--workers", type=int, default=3)
    sub.add_parser("report")
    a = ap.parse_args()
    run(a.n, a.workers) if a.cmd == "run" else report()
