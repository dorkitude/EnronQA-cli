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

Historical workshop notes follow; implementation choices above resolve their
open questions.

## Agreed requirements

- Repository: `dorkitude/EnronQA-cli`, public, MIT licensed.
- Implementation: Python using Typer (supersedes Go/Cobra). Prioritize broadly
  available Python versions on macOS and Ubuntu; see WORKSHOP_DECISIONS.md.
- Support batch evaluation through an input JSONL file.
- Support granular, call-as-needed operations for accessing questions and checking answers.
- Operations are stateless: no implicit named runs, answer history, or accumulated scores.
- Results go to stdout by default.
- JSON output is an option.
- Saving output to a file is an explicit option.
- Question retrieval excludes the reference answer by default; `--include-answer` explicitly includes it. This is a convenience for test-taking workflows, not a security boundary.
- Batch grading returns JSON containing overall accuracy, per-question correct/incorrect results, and relevant evaluation context.
- Grade only questions included in the submitted batch. Missing questions do not count as incorrect or enter the accuracy denominator.
- Issue an incompleteness warning when the batch does not cover the expected question set. Include the warning in the JSON report so stdout remains valid JSON. Coverage counts should distinguish submitted questions from the expected total. The default reference set for completeness remains to be decided.

### Proposed batch report fields (not yet agreed)

Report schema, dataset revision, split/subset, CLI/scorer versions, scoring settings, counts and explicit accuracy denominator; per-question IDs/text, submitted/reference answers, verdicts, comparison details, source email IDs, and errors. Exact schemas and invalid/duplicate-answer handling remain open.

- Dataset: the EnronQA benchmark on Hugging Face, `MichaelR207/enron_qa_0922`, pinned to revision `c0b3a9190fd970e83cfbe7d399a08860e43e221e` (last modified 2024-09-22). Every question in every split is in scope: 333,473 train, 105,515 dev, 89,316 test, 528,304 total (verified locally; matches the paper).
- Data handling: raw Enron email text and detailed source-derived artifacts (per-question ledgers containing email or answer text) stay local and git-ignored. Only scripts and aggregate reports are published. No transformed dataset is redistributed until upstream licensing is settled (see `audit/report/LICENSING.md`).
- Audit tooling: Python under `uv`; item-level semantic review uses Claude Fable via `claude -p`. Tracked in [issue #1](https://github.com/dorkitude/EnronQA-cli/issues/1).

## Illustrative command surface (not yet agreed)

```sh
enronqa score answers.jsonl
enronqa question get <question-id>
enronqa answer check <question-id> --answer '...'
```

Command names, JSONL schema, output flags, and other question metadata remain undecided. Batch and granular interfaces do not imply that the CLI launches a user's system or calls HTTP endpoints.

## Evaluation design under investigation

An audit of the EnronQA questions ([issue #1](https://github.com/dorkitude/EnronQA-cli/issues/1), pipeline in `audit/`, findings in `audit/report/`) is assessing faithful reformulations that permit deterministic answer evaluation. Candidate answer schemas under review: boolean, canonical dates and numbers with units, named entities with aliases, explicit ordered/unordered lists, structured multi-field answers, exact extraction with evidence offsets, and an explicit unconvertible class. Exact matching, normalization, structured answers, and multiple-choice transformations remain proposals, not accepted scoring requirements. Deterministic scoring alone does not establish reliable gold labels.

## Decision context

Kyle requested a public MIT Go/Cobra CLI and asked to workshop its specification before implementation. For the interface, Kyle clarified: "there shoudl be a batch format for passing a JSONL file into it. or there should be a call-as-needed set of more granular functions."

On whether individual checks should accumulate into named runs, Kyle chose: "stateless, just stdout (with json as an option and saving as another option)".

Kyle confirmed question-only retrieval by default, with `--include-answer` to reveal the reference answer.

Kyle chose overall accuracy plus per-question results: "the latter. it should be a JSON that includes all the info which may be relevant."

On incomplete batches: "only the ones it contains; but it should issue a warning that the queiton-answer set is incomplete."

## Additional decision context (Kyle's words, verbatim)

- Audit: "have a fable subagent go through all the questions to figure out if they can be rephrased to be deterministically evaluable."
