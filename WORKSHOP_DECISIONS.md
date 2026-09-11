# CLI workshop decisions

These workshop decisions are reflected in SPEC.md and the README. The latest
README-first judge design supersedes earlier lexical-scoring proposals;
implementation is tracked in CLI issues #4 and #5.

- Python and Typer; public `dorkitude/EnronQA-cli` repository, MIT license.
  This supersedes the earlier Go/Cobra requirement. Prioritize compatibility
  with Python versions researchers already use on macOS and Ubuntu.
  Proposed minimum: Python 3.10, to include Ubuntu 22.04's default Python;
  dependency compatibility must be verified before promising support. Do not
  assume a suitable Python is preinstalled on every Mac. Prefer uv for
  development; document installation for existing Python environments too.
- Dataset acquisition requires an explicit `fetch` command. Other commands
  must not silently download missing data. Fetch from the upstream host at a
  pinned revision; do not bundle or rehost the dataset in the GitHub repo.
- Missing-data errors must explain what is missing and show the exact fetch
  command needed to proceed. Fetch failures should identify the failure
  (for example network, disk space, or integrity verification) and provide an
  actionable next step without claiming the dataset is ready.
- Batch grading accepts JSONL; granular operations support call-as-needed use.
- Batch grading and standalone validation accept JSONL from stdin using `-`
  in place of a filename. Stdin input follows the same full-batch validation
  rules: consume and validate the complete input before grading begins.
- Provide a separate JSONL export of the entire email corpus for indexing in
  external systems, with stable document IDs and email text. Support stdout
  and explicit file saving. Exact metadata fields remain to be specified.
- Corpus export optionally supports sharding by documents per JSONL file;
  single-stream/single-file JSONL remains the default. Illustrative flags:
  `--shard-size 1000 --output-dir emails/`. Each shard contains up to the
  requested number of emails, rather than one file per email. Use numbered
  shard files and a manifest with dataset revision, per-file counts, and
  checksums. Exact flags and manifest schema remain proposals. Apply early
  output-conflict validation and explicit overwrite rules to sharded output.
- Support lookup of an individual email by stable document ID, returning its
  email text and available metadata. Follow the stateless stdout, optional
  JSON, and explicit file-saving conventions. Exact command name remains open.
- Export the selected question set as JSONL for a user's system to consume.
  Include stable question IDs for matching submitted answers to questions.
  As with individual question lookup, omit reference answers by default and
  include them only with `--include-answer`. Support stdout and explicit file
  saving.
- Stateless: stdout by default, optional JSON and explicit file saving.
- Explicit output files must not overwrite existing files unless `--force`
  is supplied. Check output-path conflicts and detectable writeability/path
  errors during preflight, before consuming batch input, grading, exporting,
  or other substantive work. `--force` permits replacement but must not
  truncate the existing file before successful output is ready. Preserve
  no-clobber protection at final write as well, to handle concurrent changes.
- Question lookup hides reference answers unless `--include-answer` is used.
- Question text must remain clean and match the pinned upstream EnronQA
  wording. Do not append answer-format instructions or silently replace it
  with reformulated questions in lookup/export.
- Provide a separate command to fetch answer-format and grading instructions
  for experimenters to incorporate into a system prompt or other setup.
  Return one general instruction block for the benchmark, not per-question
  instructions. Clearly label it as EnronQA-cli answer conventions, not
  instructions supplied by the upstream EnronQA dataset. The exact command
  name remains open. Instructions must not disclose reference answers.
- The reformulation audit remains research input; it does not authorize
  replacing original EnronQA questions in the CLI's standard question set.
- Question export omits the source email by default, so systems must retrieve
  evidence themselves. `--include-source` attaches the correct source email
  for debugging or evaluating answer generation with known evidence. This is
  independent of `--include-answer` and must not implicitly expose the answer.
- Batch reports are JSON with overall accuracy, per-question results, and
  relevant evaluation details.
- Preserve extra fields from submitted records (for example reasoning or
  latency) in the report, without using them for grading. Keep submitted
  metadata separate from grader-generated fields to avoid name collisions.
- Judge answer correctness using the EnronQA methodology with configurable
  LLM-as-judge and external-program integration; do not use substring matching.
- Score only submitted questions. Missing questions do not count as incorrect
  and do not enter the accuracy denominator.
- Users choose the question set. Support `all` as a selection.
- Question export supports reproducible random sampling within the selected
  set, using a sample-size option and seed (illustratively `--limit 100
  --seed 42`). Identical dataset revision, selected set, sample size, and seed
  must produce identical question selections and ordering. Exact flag names
  and seed defaults remain to be finalized.
- Batch grading and standalone validation require an explicit `--set`.
  There is no implicit default. If omitted, fail during preflight with an
  explanation and the available choices (`train`, `dev`, `test`, `all`).
  Individual question lookup and answer checking use the question ID alone
  and do not require `--set`.
- Every question in a submitted batch must belong to the selected set.
  Out-of-set questions are a validation error, not silently ignored or scored.
  Selecting `all` permits questions from any dataset set; it does not make
  nonexistent question IDs valid.
- Warn when submitted answers do not cover the entire selected set. Include
  coverage counts and the warning in the JSON report.
- Duplicate question IDs in a batch are a validation error, including when
  the submitted answers are identical.
- There are no reserved answer strings or abstention flags. All nonblank
  answers are judged normally. Missing or blank answers are validation errors.
- Batch validation collects and reports all detectable input problems in a
  single pass, with JSONL line numbers and question IDs where available,
  rather than stopping at the first invalid entry. Malformed lines must not
  prevent validation of later lines. No grading occurs if any errors exist.
- Validate the entire batch before grading begins. Malformed JSONL, invalid
  records, unknown question IDs, out-of-set IDs, and duplicate IDs reject the
  batch with an error and nonzero exit status. Do not grade a valid subset or
  emit partial scores. Missing questions remain a warning, not a validation
  error.
- Provide a standalone `validate` command to check a JSONL batch without
  grading it. It uses the same validation rules as the grading preflight,
  including selected-set membership, duplicate detection, and incomplete
  coverage warnings.

## Latest source decisions

On incomplete batches: "only the ones it contains; but it should issue a
warning that the queiton-answer set is incomplete."

On selecting sets: "CLI needs to let you choose, yes; and if you are doing
batch, the quesitons all have to live iwthin the set you chose (unless you
chose \"all\")"

## README-first decisions

The user requested a concise introduction explaining and citing EnronQA, then
short usage examples (with an installation link) before installation, followed
by complete command/option tables. Include external judge piping and built-in
OpenAI-compatible judging, using Fireworks DeepSeek V4 Flash in the example.

Built-in judge output is binary JSON, with richer prompt/output only under
`--verbose`. `--judge-prompt FILE` overrides instructions and conflicts with
built-in prompt configuration. Custom output must be pure JSON but has no
required correctness fields; place it under `judgment` in the CLI envelope.
Retry twice, then record failures; stop scheduling after five consecutive
questions exhaust retries. Keep failed/unprocessed counts separate from
accuracy. There are no special abstention strings or fields.

See SPEC.md and README.md for the intended interface. Track runtime changes in
[issue #4](https://github.com/dorkitude/EnronQA-cli/issues/4) and
[issue #5](https://github.com/dorkitude/EnronQA-cli/issues/5). Per the user's
explicit instruction, README examples describe this interface without marking
it upcoming; the open implementation issues record the remaining work.
