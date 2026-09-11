"""Evaluate saved retrievals only after predictions have been written.

Run with uv run --no-project python experiments/trial_metrics.py WORK_DIR.
Requires answer-key.jsonl (same sampled export with --include-answer),
baseline-report.json and manual-report.json produced by the released CLI.
"""

import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
key = {
    r["question_id"]: r
    for r in map(json.loads, (root / "answer-key.jsonl").read_text().splitlines())
}
hits = list(map(json.loads, (root / "retrievals.jsonl").read_text().splitlines()))
ranks = []
for row in hits:
    target = key[row["question_id"]]["document_id"]
    ranks.append(
        row["document_ids"].index(target) + 1 if target in row["document_ids"] else None
    )
metrics = {
    "sample": len(hits),
    "exact_source_document_recall": {
        str(k): sum(r is not None and r <= k for r in ranks) / len(ranks)
        for k in (1, 5, 10)
    },
    "mrr_at_10": sum(1 / r if r else 0 for r in ranks) / len(ranks),
    "answer_summary": json.loads((root / "baseline-report.json").read_text())[
        "summary"
    ],
    "manual_summary": json.loads((root / "manual-report.json").read_text())["summary"],
    "timing": json.loads((root / "timing.json").read_text()),
}
(root / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
print(json.dumps(metrics, indent=2))
