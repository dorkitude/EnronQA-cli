# EnronQA-cli

Tooling around the [EnronQA](https://arxiv.org/abs/2505.00263) benchmark
(Ryan, Xu, Nivera, Campos, 2025) with the goal of **deterministic evaluation**:
verdicts that do not depend on an LLM judge.

Status: specification is being workshopped. See [`SPEC.md`](SPEC.md) for what is
agreed and what is not, and [issue #1](https://github.com/dorkitude/EnronQA-cli/issues/1)
for the ongoing audit of whether every question can be reformulated into a
deterministically scorable form.

## Layout

- `SPEC.md` — agreed requirements and open questions.
- `audit/` — reusable audit pipeline (`uv` project). Scripts are published;
  the per-question ledger and any file containing email or answer text stay
  local and git-ignored.
- `audit/report/` — aggregate findings that contain no email text.
- `data/` — local only. `data/raw` points at the pinned dataset revision.

## Reproducing the audit

```bash
cd audit
uv sync
# download the pinned revision (see audit/scripts/00_download.sh)
bash scripts/00_download.sh
uv run scripts/01_enumerate.py      # per-question ledger with stable IDs (local)
uv run scripts/02_screen.py         # programmatic screening features (local)
uv run scripts/03_semantic_review.py --help   # Claude Fable item-level review
uv run scripts/04_aggregate.py      # aggregate report -> audit/report/
```

## License

MIT for the code in this repository. The EnronQA dataset and the underlying
Enron corpus have their own terms; see `audit/report/LICENSING.md`.
