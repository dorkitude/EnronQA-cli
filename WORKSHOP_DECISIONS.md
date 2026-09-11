# CLI workshop decisions

These user-confirmed decisions supplement SPEC.md and take precedence over
older open questions there. Implementation remains pending spec agreement.

- Go and Cobra; public `dorkitude/EnronQA-cli` repository, MIT license.
- Batch grading accepts JSONL; granular operations support call-as-needed use.
- Export the selected question set as JSONL for a user's system to consume.
  Include stable question IDs for matching submitted answers to questions.
  As with individual question lookup, omit reference answers by default and
  include them only with `--include-answer`. Support stdout and explicit file
  saving.
- Stateless: stdout by default, optional JSON and explicit file saving.
- Question lookup hides reference answers unless `--include-answer` is used.
- Question export omits the source email by default, so systems must retrieve
  evidence themselves. `--include-source` attaches the correct source email
  for debugging or evaluating answer generation with known evidence. This is
  independent of `--include-answer` and must not implicitly expose the answer.
- Batch reports are JSON with overall accuracy, per-question results, and
  relevant evaluation details.
- Score only submitted questions. Missing questions do not count as incorrect
  and do not enter the accuracy denominator.
- Users choose the question set. Support `all` as a selection.
- Every question in a submitted batch must belong to the selected set.
  Out-of-set questions are a validation error, not silently ignored or scored.
  Selecting `all` permits questions from any dataset set; it does not make
  nonexistent question IDs valid.
- Warn when submitted answers do not cover the entire selected set. Include
  coverage counts and the warning in the JSON report.
- Duplicate question IDs in a batch are a validation error, including when
  the submitted answers are identical.
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

## Still open

Exact command names, JSON schemas, default/required set selection, validation
error report details, and deterministic answer conversion and scoring policies.
