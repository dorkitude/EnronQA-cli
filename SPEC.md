# EnronQA-cli specification

Status: v0.1 implementation authorized September 11, 2026. The runnable command
surface and report schema are documented in README.md. WORKSHOP_DECISIONS.md
preserves the design conversation; the release decisions below supersede older
open proposals in this document.

## v0.1 release decisions

- Python 3.10+, Typer; `questions get/export`, `documents get/export`, `fetch`,
  `instructions`, `validate`, `score`, `check`.
- Explicit `--set train|dev|test|all` for exports and batches; no batch default.
- `normalized-exact` (NFC, casefold, whitespace collapse) or `exact` scoring
  against unmodified upstream gold/alternate answers. This is lexical accuracy,
  not semantic correctness and not a reproduction of paper LLM-judge scoring.
- Original questions stay unchanged. Question IDs are opaque SHA-256 of
  `revision/split/path/zero-based-index`, rather than audit path identifiers.
- Default question output hides answers, source email, and source document ID.
- `--limit` samples without replacement, `--seed` defaults to 0, with output
  sorted by stable question ID for a reproducible selection and order.
- Batch reports always JSON, schema version 1. Invalid batches exit 2, contain
  all detectable validation errors, and contain no partial grades.
- JSONL records require question_id and nonblank string answer; additional
  fields are preserved under per-result metadata. Abstention is normalized
  `I don't know`, always incorrect. All other answers use the selected scorer.
- Cache is configurable with --data-dir / ENRONQA_DATA_DIR. Fetch verifies four
  pinned SHA-256 checksums and builds a local SQLite index. No implicit fetch.
- Optional --shard-size requires --output-dir. --force only replaces a directory
  entirely owned by a prior export manifest, preserving unrelated files.


## Repository scope

This repository owns the self-contained CLI: runtime code, product tests,
packaging, user documentation, and interface specifications. Research
experiments, benchmark runs, dataset-reformulation audits, and their results
belong in a separate research workspace.
