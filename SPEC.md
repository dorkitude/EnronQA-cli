# EnronQA-cli — Specification (workshop draft)

Status: **not agreed**. This file records only requirements Kyle Wild has
explicitly agreed to, plus a clearly separated list of open questions. Nothing
under "Undecided" is a commitment. The CLI is **not** to be implemented until
this spec is agreed.

## Agreed requirements

1. **Repository.** `dorkitude/EnronQA-cli`, public, MIT license, added as a git
   submodule of Kyle's research workspace.
2. **Implementation target.** A Go CLI built with Cobra.
3. **Dataset.** The EnronQA benchmark from Hugging Face,
   `MichaelR207/enron_qa_0922`, pinned to revision
   `c0b3a9190fd970e83cfbe7d399a08860e43e221e` (last modified 2024-09-22).
   Every question in every split is in scope: 333,473 train, 105,515 dev,
   89,316 test, 528,304 total (verified locally; matches the paper).
4. **Goal.** Questions must be evaluable deterministically: given a system
   answer and the reference, the verdict must be reproducible without an LLM
   judge. Whether every question *can* be reformulated to allow this, without
   changing the information need, is the subject of the audit tracked in
   [issue #1](https://github.com/dorkitude/EnronQA-cli/issues/1).
5. **Data handling.** Raw Enron email text and detailed source-derived
   artifacts (per-question ledgers containing email or answer text) stay local
   and git-ignored. Only scripts and aggregate reports are published. No
   transformed dataset is redistributed until upstream licensing is settled
   (see `audit/report/LICENSING.md`).
6. **Tooling.** Python audit code runs under `uv`. Item-level semantic review
   uses Claude Fable through `claude -p`.

## Undecided (proposals only, see the audit report)

- Answer schema taxonomy and the exact normalization rules per schema
  (dates, numbers with units, entity aliases, list ordering, multi-field).
- Whether multiple choice built from the supplied `incorrect_answers` is a
  supported evaluation mode, given that it changes the task.
- Scoring function(s): exact match after normalization, set/list scoring,
  partial credit for multi-field answers, evidence-offset checks.
- CLI command surface, input/output formats, and how reformulated items are
  stored and versioned.
- Which subset of items (if any) is excluded as unconvertible, and the
  acceptance criteria for a reformulated item.
- The broader Word Sense Induction line of work over the Enron corpus is the
  motivating context, but its relationship to this CLI is not yet specified.
