# EnronQA-cli

A command-line test bench for search and question answering over Enron emails.
Export questions, submit answers, and get a JSON report with overall accuracy
and individual results.

**Scoring scope:** v0.1 measures deterministic **lexical agreement**, not semantic
answer correctness or the original paper's LLM-judge accuracy. Valid paraphrases
can fail. Questions are never rewritten. The default `normalized-exact` scorer
compares the submitted answer with upstream gold and alternate answers after
Unicode NFC normalization, case folding, and whitespace collapse. Punctuation,
numbers, and negation remain significant. Use `--scorer exact` for literal
string equality. Substring matching is never used.

## Install

### macOS with Homebrew

```bash
brew install dorkitude/tap/enronqa-cli
enronqa --version
```

Homebrew installs Python and dependencies for you in an isolated environment.

### Ubuntu 22.04+ (amd64) with apt

```bash
curl -fLO https://github.com/dorkitude/EnronQA-cli/releases/download/v0.1.0/enronqa-cli_0.1.0_amd64.deb
sudo apt install ./enronqa-cli_0.1.0_amd64.deb
enronqa --version
```

This downloadable `.deb` includes its own Python runtime and dependencies;
it does not change system Python. There is no hosted apt repository or
automatic release upgrade channel yet. Download a newer `.deb` to upgrade.

### Existing Python 3.10+ or uv

```bash
uv tool install 'https://github.com/dorkitude/EnronQA-cli/releases/download/v0.1.0/enronqa_cli-0.1.0-py3-none-any.whl'
```

Alternatively, use `pip install` with the same wheel URL inside your existing
Python virtual environment. No PyPI publication is required. A suitable Python
is not necessarily preinstalled on macOS; Homebrew or uv can provide it.
All installation methods install the CLI only. Run `enronqa fetch` explicitly
to obtain the dataset. Release assets include `SHA256SUMS` for verification.

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
and explicit overwrite policy. `--force` can replace a previous sharded export
only when its directory contains exactly the files listed in its manifest;
unrelated files cause an error. Completed shards are staged before publication.
Consumers should wait for command success before reading a sharded export.

## Answer files

JSONL format: one answer per line, identified by question ID. These IDs
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

Reports use `schema_version: "1"` and include:

| Section | Contents |
| --- | --- |
| Provenance | Report schema, CLI/scorer versions, dataset revision, selected set, comparison settings |
| Summary | Submitted/correct/incorrect/abstained counts; accuracy with an explicit numerator and denominator |
| Coverage | Expected and submitted counts; incompleteness warnings |
| Per question | ID, original question, submitted and reference answers, verdict, abstention flag, comparison details, source document ID |
| Submitted metadata | Extra input fields retained without affecting grading or overwriting grader fields |

Accuracy describes the submitted batch, not unsubmitted questions. It is a
fraction between 0 and 1 under `summary.accuracy`. `summary.denominator` includes
abstentions. Failed validation returns `valid: false`, an `errors` array, and no
scores (exit 2). Successful validation/grading exits 0 even when answers are wrong.
Scoring reports disclose reference answers and correct document IDs; keep them
out of your system's test-taking inputs.

## Implementation and data

The CLI uses Python 3.10+ and Typer, with PyArrow for Parquet ingestion. No Go,
model runtime, API key, or LLM service is required. Development uses `uv sync`,
`uv run pytest`, and `uv build`. The Python API is reusable:

```python
from enronqa.data import Dataset
from enronqa.scoring import validation, score

with Dataset() as dataset, open("answers.jsonl", "rb") as answers:
    records, report = validation(answers, dataset, "test")
    if report["valid"]:
        report = score(records, report, dataset)
```

`fetch` downloads and SHA-256 verifies the pinned upstream
[EnronQA dataset](https://huggingface.co/datasets/MichaelR207/enron_qa_0922)
revision `c0b3a9190fd970e83cfbe7d399a08860e43e221e`, then builds a local SQLite
index. Other commands never download data. The corpus is not bundled here.
Allow several GB of free space for downloads, the index, and temporary files.
The cache defaults to `$XDG_CACHE_HOME/enronqa` or `~/.cache/enronqa`.
Override it with `ENRONQA_DATA_DIR` or a command's `--data-dir PATH` option.

There are 528,304 questions: 333,473 train, 105,515 dev, and 89,316 test.
Corpus export deduplicates repeated upstream rows by email path, producing
73,772 unique emails. Document IDs are original paths. Public question IDs are
SHA-256 hashes of `revision/split/path/question-index` (zero-based index), stable
for this pinned revision, so the ID itself does not reveal the source path.
The split is question-level: emails can occur in multiple splits. This is not
an unseen-email generalization benchmark without additional experimental design.

Exports stream records. Batch validation retains submissions and grading retains
a complete report in memory; very large batches therefore require memory
proportional to their answer and metadata size. There is no implicit saved run.

## License and attribution

Repository code is MIT licensed. That license does not cover the EnronQA
dataset or underlying email corpus; see [licensing findings](docs/DATASET_LICENSING.md).

Benchmark: Michael J. Ryan, Danmei Xu, Chris Nivera, and Daniel Campos.
[EnronQA: Towards Personalized RAG over Private Documents](https://arxiv.org/abs/2505.00263), 2025.
