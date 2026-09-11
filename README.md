# EnronQA-cli

A command-line test bench for search and question answering over Enron emails.
Export questions, submit answers, and get a JSON report with overall accuracy
and individual results.

**Design preview:** the CLI is not implemented yet. Commands and JSON schemas
below are proposals for review, not runnable instructions. Agreed behavior is
recorded in [WORKSHOP_DECISIONS.md](WORKSHOP_DECISIONS.md), which supplements
[SPEC.md](SPEC.md). Answer comparison rules are still being designed; this tool
must not claim to reproduce the original paper's scores without matching its
protocol.

## Batch workflow

```bash
# Explicitly download the pinned upstream dataset into a local cache.
enronqa fetch

# Export the email corpus for your system to index.
enronqa documents export --output emails.jsonl

# Export questions for your system to answer.
enronqa questions export --set test --output questions.jsonl

# Get shared answer conventions to incorporate into your system prompt.
enronqa instructions

# Your system produces answers.jsonl.
# Check the whole file without grading it.
enronqa validate answers.jsonl --set test --json

# Validate first, then grade and save a comprehensive JSON report.
enronqa score answers.jsonl --set test --output report.json
```

The CLI does not launch your system or manage experiment runs. Dataset caching
is local setup; evaluation calls do not accumulate answer history or scores.

### Optional corpus sharding

Single-file (or stdout) JSONL is the default and can be read one email at a
time. For smaller imports and transfers, optionally split the corpus into
multiple files:

```bash
enronqa documents export --shard-size 1000 --output-dir emails/
```

This writes up to 1,000 emails per numbered JSONL file, plus a manifest with
the dataset revision, per-file counts, and checksums. It does not create one
file per email. Sharded export follows the same early output-conflict checks
and explicit overwrite policy. Flag names and manifest schema are proposals.

## Answer files

Proposed JSONL format: one answer per line, identified by question ID. These IDs
and values are illustrative, not actual benchmark records.

```jsonl
{"question_id":"<id-1>","answer":"<your answer>","reasoning":"<optional explanation>","latency_ms":120}
{"question_id":"<id-2>","answer":"I don't know"}
```

Only the answer is graded. Extra fields are preserved separately in the report.
Use `I don't know` for an abstention: it counts as incorrect and is identified
in the report. Missing or blank answers are validation errors.

Piped input works too; the complete stream is validated before grading:

```bash
cat answers.jsonl | enronqa score - --set test
cat answers.jsonl | enronqa validate - --set test --json
```

## Granular workflow

```bash
# Fetch a question without its reference answer or source email.
enronqa questions get '<question-id>' --json

# Inspect an email returned by your own retriever.
enronqa documents get '<document-id>' --json

# Check one answer; no named run or saved state is created.
enronqa check '<question-id>' --answer '<your answer>' --json
```

Question text stays exactly as supplied by the pinned EnronQA dataset. The
`instructions` command returns one shared block describing EnronQA-cli's
conventions, clearly distinguished from upstream benchmark instructions.
Instructions are not appended to questions.

## Select questions and inspect evidence

The dataset provides `train`, `dev`, and `test` groups. Choose `all` to include
all three. Batch validation and grading require `--set`; there is no default.
Individual lookups and checks require only an ID.

```bash
# Export a reproducible random sample.
enronqa questions export --set test --limit 100 --seed 42 --output sample.jsonl

# Opt into reference answers or correct source emails independently.
enronqa questions export --set test --include-answer --output answer-key.jsonl
enronqa questions export --set test --include-source --output questions-with-evidence.jsonl
```

`--include-source` gives the system the correct email, bypassing the retrieval
step. Leave it off when evaluating retrieval. `--include-answer` reveals the
answer key. Neither is enabled by default.

A sampled submission is scored on its submitted questions, with an incomplete
coverage warning relative to the selected set. Reusing the same dataset
revision, set, sample size, and seed produces the same selection and order.

## Validation and output behavior

Before reading a batch or doing substantive work, the CLI checks required
arguments, local data availability, and the output destination. It then
validates the complete batch before grading any answers.

- Malformed JSONL, missing/blank answers, unknown IDs, out-of-set IDs, and
  duplicate IDs reject the entire batch with a nonzero exit status.
- Validation lists all detectable input errors with line numbers and question
  IDs where available. It does not stop at the first malformed line.
- Missing questions produce a coverage warning, not an error. Only submitted
  questions enter the accuracy denominator.
- `--set all` permits IDs from any group, but does not permit nonexistent IDs.
- Output goes to stdout by default. Batch scores are JSON; other operations
  support JSON output, and data exports are JSONL.
- `--output` explicitly saves a file. Existing files cause an early error
  unless `--force` is supplied. Replacement must not destroy an existing file
  before successful output is ready.

For example, missing local data should give an actionable error:

```text
EnronQA data is not available locally.
Run: enronqa fetch
```

## Score report

The final schema remains open. The proposed report includes:

| Section | Contents |
| --- | --- |
| Provenance | Report schema, CLI/scorer versions, dataset revision, selected set, comparison settings |
| Summary | Submitted/correct/incorrect/abstained counts; accuracy with an explicit numerator and denominator |
| Coverage | Expected and submitted counts; incompleteness warnings |
| Per question | ID, original question, submitted and reference answers, verdict, abstention flag, comparison details, source document ID |
| Submitted metadata | Extra input fields retained without affecting grading or overwriting grader fields |

Accuracy describes the submitted batch, not unsubmitted questions. Exact
matching, normalization, and other deterministic comparison policies remain
under review. Universal substring matching is not an agreed rule: a response
can contain the expected text while contradicting it.

## Implementation and data

The planned CLI is written in Go using Cobra. Installation instructions will
be added when an implementation is available.

`fetch` downloads a pinned revision from the upstream
[EnronQA dataset](https://huggingface.co/datasets/MichaelR207/enron_qa_0922).
Other commands do not silently download data. The corpus is not bundled in
this repository. Dataset cache location and configuration remain open.

## Research audit

[Issue #1](https://github.com/dorkitude/EnronQA-cli/issues/1) tracks the audit of
whether questions can support faithful deterministic evaluation. This research
does not authorize replacing original questions in the CLI's standard export.
See [audit/report](audit/report) for findings and coverage limitations.

Audit scripts are separate Python tooling, run with `uv`:

```bash
cd audit
uv sync
bash scripts/00_download.sh
uv run scripts/01_enumerate.py
uv run scripts/02_screen.py
uv run scripts/03_semantic_review.py --help
uv run scripts/04_aggregate.py
```

Raw data and source-derived per-question ledgers remain local and git-ignored.

## License and attribution

Repository code is MIT licensed. That license does not cover the EnronQA
dataset or underlying email corpus; see [licensing findings](audit/report/LICENSING.md).

Benchmark: Michael J. Ryan, Danmei Xu, Chris Nivera, and Daniel Campos.
[EnronQA: Towards Personalized RAG over Private Documents](https://arxiv.org/abs/2505.00263), 2025.
