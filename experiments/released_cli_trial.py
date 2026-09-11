"""Local retrieval smoke experiment using only EnronQA-cli exports.

Run: uv run --no-project python experiments/released_cli_trial.py WORK_DIR
WORK_DIR must contain emails.jsonl and questions.jsonl exported by the CLI.
No answer key is used. Writes local FTS index, retrievals and answer submissions.
This deliberately simple baseline is not an embedding or WSI experiment.
"""

import json
import re
import sqlite3
import sys
import time
from pathlib import Path

STOP = set(
    "a an and are as at be by did do does for from had has have how i in is it its of on or that the their there these they this to was were what when where which who why will with would you your".split()
)


def terms(s):
    return [
        w for w in re.findall(r"[^\W_]+", s.lower()) if len(w) > 1 and w not in STOP
    ]


def main(root):
    started = time.perf_counter()
    db = sqlite3.connect(root / "retrieval.sqlite")
    db.execute(
        'CREATE VIRTUAL TABLE emails USING fts5(document_id UNINDEXED, email, tokenize="unicode61")'
    )
    count = 0
    with (root / "emails.jsonl").open() as stream:
        for line in stream:
            row = json.loads(line)
            db.execute(
                "INSERT INTO emails VALUES (?,?)", (row["document_id"], row["email"])
            )
            count += 1
    db.commit()
    indexed = time.perf_counter()
    with (
        (root / "questions.jsonl").open() as questions,
        (root / "retrievals.jsonl").open("w") as hits,
        (root / "answers.jsonl").open("w") as answers,
    ):
        for line in questions:
            q = json.loads(line)
            qt = list(dict.fromkeys(terms(q["question"])))[:32]
            query = " OR ".join('"' + t + '"' for t in qt)
            rows = (
                db.execute(
                    "SELECT document_id,email,bm25(emails) FROM emails WHERE emails MATCH ? ORDER BY bm25(emails),document_id LIMIT 10",
                    (query,),
                ).fetchall()
                if query
                else []
            )
            # Extract a high-overlap sentence from the top retrieved email.
            sentences = re.split(r"(?<=[.!?])\s+|\n+", rows[0][1]) if rows else []
            sentences = [s.strip() for s in sentences if s.strip()]
            answer = (
                max(sentences, key=lambda s: len(set(terms(s)) & set(qt)))
                if sentences
                else "I don't know"
            )
            ids = [r[0] for r in rows]
            hits.write(
                json.dumps(
                    {
                        "question_id": q["question_id"],
                        "query": query,
                        "document_ids": ids,
                    }
                )
                + "\n"
            )
            answers.write(
                json.dumps(
                    {
                        "question_id": q["question_id"],
                        "answer": answer,
                        "method": "fts5-bm25-top1-overlap-sentence",
                        "retrieved_document_ids": ids,
                    }
                )
                + "\n"
            )
    result = {
        "documents": count,
        "index_seconds": indexed - started,
        "retrieval_seconds": time.perf_counter() - indexed,
        "fts_bytes": (root / "retrieval.sqlite").stat().st_size,
    }
    (root / "timing.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
