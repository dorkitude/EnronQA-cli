"""Stage 1: enumerate every question in every split into a per-question ledger.

Outputs (local, git-ignored):
  ledger/questions.parquet  one row per question, stable id `qid = split/path/qidx`
  ledger/emails.parquet     one row per unique email (identical across splits), keyed by path
  report/counts.json        verified counts (no email or answer text)
"""
import hashlib, json, sys
import polars as pl
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import SPLITS, LEDGER, REPORT, load_split

frames, email_frames, counts = [], [], {}
for split in SPLITS:
    df = load_split(split)
    counts[split] = {
        "rows": df.height,
        "rows_with_zero_questions": int((df["questions_count"] == 0).sum()),
        "questions": int(df["questions_count"].sum()),
        "unique_paths": df["path"].n_unique(),
        "users": df["user"].n_unique(),
    }
    email_frames.append(df.select("path", "user", "email"))
    ex = (
        df.filter(pl.col("questions_count") > 0)
        .with_columns(qidx=pl.int_ranges(0, pl.col("questions_count")))
        .explode(["qidx", "questions", "rephrased_questions", "gold_answers", "alternate_answers",
                  "incorrect_answers", "gold_rationales", "alternate_rationales", "include_email"])
        .select(
            qid=pl.lit(split) + "/" + pl.col("path") + "/" + pl.col("qidx").cast(pl.Utf8),
            split=pl.lit(split), user="user", path="path", qidx="qidx",
            question="questions", rephrased_question="rephrased_questions", gold="gold_answers",
            alternates="alternate_answers", incorrects="incorrect_answers",
            gold_rationale="gold_rationales", alternate_rationales="alternate_rationales",
            include_email="include_email",
        )
    )
    assert ex.height == counts[split]["questions"], (split, ex.height)
    frames.append(ex)

q = pl.concat(frames)
q = q.with_columns(
    content_sha1=pl.concat_str([pl.col("question"), pl.lit("\x1f"), pl.col("gold")]).map_elements(
        lambda s: hashlib.sha1(s.encode()).hexdigest(), return_dtype=pl.Utf8),
)
assert q["qid"].n_unique() == q.height, "qid collision"
q.write_parquet(LEDGER / "questions.parquet")

em = pl.concat(email_frames).unique(subset=["path"], keep="first")
# verify email text identical across splits
allp = pl.concat(email_frames)
assert allp.group_by("path").agg(pl.col("email").n_unique().alias("n"))["n"].max() == 1, "email text differs across splits"
em = em.with_columns(
    email_sha1=pl.col("email").map_elements(lambda s: hashlib.sha1(s.encode()).hexdigest(), return_dtype=pl.Utf8),
    email_chars=pl.col("email").str.len_chars(),
)
em.write_parquet(LEDGER / "emails.parquet")

counts["total_questions"] = int(q.height)
counts["unique_emails"] = em.height
counts["paper_claims"] = {"total_questions": 528304, "emails": 103638, "train": 333473, "dev": 105515, "test": 89316}
counts["email_text_identical_across_splits"] = True
counts["duplicate_question_text_within_split"] = {
    s: int(q.filter(pl.col("split") == s).height - q.filter(pl.col("split") == s)["question"].n_unique()) for s in SPLITS}
counts["duplicate_qid_content_sha1_across_all"] = int(q.height - q["content_sha1"].n_unique())
json.dump(counts, open(REPORT / "counts.json", "w"), indent=2)
print(json.dumps(counts, indent=2))
