"""Stage 3: item-level semantic review with Claude Fable via `claude -p`.

Batch unit = one email plus ALL its questions across the three splits (the same
73,772 emails appear in every split). Several emails are packed per call.

  uv run scripts/03_semantic_review.py plan                 # build work/batches/*.json (local)
  uv run scripts/03_semantic_review.py run --workers 4 --limit 50
  uv run scripts/03_semantic_review.py status
  uv run scripts/03_semantic_review.py collect              # -> ledger/semantic.parquet

Every batch result (raw model output + parse status) is cached under cache/reviews/.
Re-running `run` skips finished batches. Coverage is therefore exact and resumable.
"""
import argparse, json, os, subprocess, sys, time, re, random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import polars as pl
sys.path.insert(0, str(Path(__file__).parent))
from common import LEDGER, WORK, CACHE, REPORT, questions, emails

BATCH_DIR = WORK / "batches"; BATCH_DIR.mkdir(exist_ok=True)
REV_DIR = CACHE / "reviews"; REV_DIR.mkdir(exist_ok=True)
PROMPT = (Path(__file__).parent / "review_prompt.md").read_text()
import hashlib
PROMPT_SHA = hashlib.sha1(PROMPT.encode()).hexdigest()[:10]
MODEL = os.environ.get("REVIEW_MODEL", "claude-fable-5-1")
EFFORT = os.environ.get("REVIEW_EFFORT", "low")
MAX_CHARS = int(os.environ.get("REVIEW_MAX_CHARS", "48000"))   # ~12k tokens of payload per call
MAX_EMAILS = int(os.environ.get("REVIEW_MAX_EMAILS", "8"))
EMAIL_CLIP = int(os.environ.get("REVIEW_EMAIL_CLIP", "12000"))  # chars; long emails are clipped, flagged in batch


def plan():
    q = questions().select("qid", "path", "question", "gold", "alternates", "incorrects").sort(["path", "qid"])
    em = emails().select("path", "email").sort("path")
    groups = {p: [] for p in em["path"].to_list()}
    for r in q.iter_rows(named=True):
        groups[r["path"]].append(r)
    emails_text = dict(zip(em["path"].to_list(), em["email"].to_list()))
    # deterministic but split-balanced order: shuffle emails with a fixed seed so any prefix is a fair sample
    paths = sorted(groups); random.Random(20260911).shuffle(paths)
    batches, cur, cur_chars = [], [], 0
    for p in paths:
        items = groups[p]
        if not items:
            continue
        etext = emails_text[p]
        clipped = len(etext) > EMAIL_CLIP
        etext = etext[:EMAIL_CLIP]
        size = len(etext) + sum(len(i["question"]) + len(i["gold"]) + len(i["alternates"][0]) + sum(map(len, i["incorrects"])) for i in items)
        if cur and (cur_chars + size > MAX_CHARS or len(cur) >= MAX_EMAILS):
            batches.append(cur); cur, cur_chars = [], 0
        cur.append({"path": p, "email": etext, "email_clipped": clipped,
                    "items": [{"qid": i["qid"], "q": i["question"], "gold": i["gold"], "alt": i["alternates"][0], "inc": i["incorrects"]} for i in items]})
        cur_chars += size
    if cur:
        batches.append(cur)
    for n, b in enumerate(batches):
        (BATCH_DIR / f"{n:06d}.json").write_text(json.dumps(b, ensure_ascii=False))
    nq = sum(len(e["items"]) for b in batches for e in b)
    print(f"planned {len(batches)} batches covering {nq} questions over {sum(len(b) for b in batches)} emails")


def render(batch):
    out = []
    k = 0
    for e in batch:
        out.append(f"=== EMAIL {e['path']}{' (clipped)' if e['email_clipped'] else ''} ===\n{e['email']}\n")
        for it in e["items"]:
            out.append(f"--- ITEM i={k} (email {e['path']})\nQ: {it['q']}\nGOLD: {it['gold']}\nALT: {it['alt']}\nINCORRECT_1: {it['inc'][0]}\nINCORRECT_2: {it['inc'][1]}\n")
            it["i"] = k; k += 1
    return "\n".join(out), k


def run_one(bfile: Path):
    out = REV_DIR / (bfile.stem + ".json")
    if out.exists():
        return bfile.stem, "cached"
    batch = json.loads(bfile.read_text())
    text, n = render(batch)
    cmd = ["claude", "-p", "--no-session-persistence", "--model", MODEL, "--effort", EFFORT,
           "--output-format", "json", "--tools", "", "--system-prompt", PROMPT]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, input=f"Review these {n} items.\n\n{text}", capture_output=True, text=True, timeout=1800)
        raw = proc.stdout
        meta = json.loads(raw) if raw.strip().startswith("{") else {"result": raw}
        result = meta.get("result", "")
        parsed, err = parse_result(result, n)
        rec = {"batch": bfile.stem, "n_items": n, "elapsed_s": round(time.time() - t0, 1), "returncode": proc.returncode,
               "usage": meta.get("usage"), "cost_usd_list": meta.get("total_cost_usd"), "model": MODEL, "effort": EFFORT, "prompt_sha": PROMPT_SHA,
               "parse_error": err, "items": parsed, "raw_result": result if err else None, "stderr": proc.stderr[-2000:] if proc.returncode else None}
    except subprocess.TimeoutExpired:
        rec = {"batch": bfile.stem, "n_items": n, "elapsed_s": round(time.time() - t0, 1), "returncode": -1, "parse_error": "timeout", "items": []}
    # map item index -> qid
    idx = {it["i"]: it["qid"] for e in batch for it in e["items"]}
    for it in rec["items"]:
        it["qid"] = idx.get(it.get("i"))
    # transient failures (auth, rate limit, empty result) are NOT cached so they are retried on the next run
    blob = (rec.get("raw_result") or "") + (rec.get("stderr") or "")
    transient = rec["returncode"] != 0 or rec["parse_error"] == "timeout" or (not rec["items"] and re.search(
        r"rate.?limit|usage limit|overloaded|Not logged in|429|529|network|ECONN|timed out", blob, re.I))
    if transient:
        (WORK / "failures.log").open("a").write(json.dumps({"batch": bfile.stem, "t": time.time(), "rc": rec["returncode"], "err": rec["parse_error"], "msg": blob[:300]}) + "\n")
        return bfile.stem, f"TRANSIENT rc={rec['returncode']} err={rec['parse_error']} msg={blob[:120]!r}"
    out.write_text(json.dumps(rec, ensure_ascii=False))
    return bfile.stem, f"ok n={n} parsed={len(rec['items'])} err={rec['parse_error']} {rec['elapsed_s']}s"


def parse_result(result: str, n: int):
    s = result.strip()
    m = re.search(r"\[.*\]", s, re.S)
    if not m:
        return [], "no_json_array"
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return [], f"json_error:{e}"
    good = [a for a in arr if isinstance(a, dict) and isinstance(a.get("i"), int) and 0 <= a["i"] < n]
    err = None if len(good) == n else f"count_mismatch:{len(good)}/{n}"
    return good, err


def run(workers: int, limit: int | None):
    files = sorted(BATCH_DIR.glob("*.json"))
    todo = [f for f in files if not (REV_DIR / (f.stem + ".json")).exists()]
    if limit:
        todo = todo[:limit]
    print(f"{len(files)} batches planned, {len(list(REV_DIR.glob('*.json')))} done, running {len(todo)} now with {workers} workers", flush=True)
    consecutive_fail = 0
    stop = False
    def guarded(f):
        nonlocal consecutive_fail, stop
        if stop:
            return f.stem, "skipped (circuit open)"
        stem, msg = run_one(f)
        if msg.startswith("TRANSIENT"):
            consecutive_fail += 1
            if consecutive_fail >= 12:
                stop = True
            time.sleep(min(300, 15 * consecutive_fail))
        else:
            consecutive_fail = 0
        return stem, msg
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(guarded, f) for f in todo]
        for fut in as_completed(futs):
            print(time.strftime("%H:%M:%S"), *fut.result(), flush=True)
    if stop:
        print("CIRCUIT OPEN: 12 consecutive transient failures; stopped. Re-run to resume.", flush=True)


def status():
    files = sorted(BATCH_DIR.glob("*.json")); done = sorted(REV_DIR.glob("*.json"))
    n_items = n_parsed = n_err = 0; secs = 0
    for d in done:
        r = json.loads(d.read_text()); n_items += r["n_items"]; n_parsed += len(r["items"]); secs += r.get("elapsed_s", 0)
        n_err += bool(r.get("parse_error"))
    total_q = sum(len(e["items"]) for f in files for e in json.loads(f.read_text())) if files else 0
    print(json.dumps({"batches_planned": len(files), "batches_done": len(done), "batches_with_parse_error": n_err,
                      "questions_planned": total_q, "questions_in_done_batches": n_items, "questions_parsed": n_parsed,
                      "mean_batch_seconds": round(secs / len(done), 1) if done else None}, indent=2))


def collect():
    rows = []
    for d in sorted(REV_DIR.glob("*.json")):
        r = json.loads(d.read_text())
        for it in r["items"]:
            if not it.get("qid"):
                continue
            canon = it.get("canon")
            rows.append({"qid": it["qid"], "batch": r["batch"], "cat": str(it.get("cat")), "verdict": str(it.get("verdict")),
                         "conf": str(it.get("conf")), "flags": [str(f) for f in (it.get("flags") or [])],
                         "canon": canon if isinstance(canon, str) else json.dumps(canon, ensure_ascii=False),
                         "aliases": [str(a) for a in (it.get("aliases") or [])], "rq": it.get("rq"), "note": it.get("note"),
                         "narrowed": it.get("narrowed") if isinstance(it.get("narrowed"), bool) else None,
                         "model": r.get("model"), "effort": r.get("effort"), "prompt_sha": r.get("prompt_sha")})
    df = pl.DataFrame(rows, schema_overrides={"rq": pl.Utf8, "note": pl.Utf8, "narrowed": pl.Boolean, "prompt_sha": pl.Utf8})
    df = df.unique(subset=["qid"], keep="last")
    df.write_parquet(LEDGER / "semantic.parquet")
    print("semantic rows", df.height)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan"); sub.add_parser("status"); sub.add_parser("collect")
    r = sub.add_parser("run"); r.add_argument("--workers", type=int, default=3); r.add_argument("--limit", type=int)
    a = ap.parse_args()
    {"plan": plan, "status": status, "collect": collect, "run": lambda: run(a.workers, a.limit)}[a.cmd]()
