# EnronQA-cli: draft specification

Status: workshopping with Kyle Wild; implementation has not been approved to begin.

## Agreed requirements

- Repository: `dorkitude/EnronQA-cli`, public, MIT licensed.
- Implementation: Go using Cobra.
- Support batch evaluation through an input JSONL file.
- Support granular, call-as-needed operations for accessing questions and checking answers.
- Operations are stateless: no implicit named runs, answer history, or accumulated scores.
- Results go to stdout by default.
- JSON output is an option.
- Saving output to a file is an explicit option.
- Question retrieval excludes the reference answer by default; `--include-answer` explicitly includes it. This is a convenience for test-taking workflows, not a security boundary.

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
