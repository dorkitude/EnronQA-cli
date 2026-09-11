# CLI workshop decisions

These user-confirmed decisions supplement SPEC.md and take precedence over
older open questions there. Implementation remains pending spec agreement.

- Go and Cobra; public `dorkitude/EnronQA-cli` repository, MIT license.
- Batch grading accepts JSONL; granular operations support call-as-needed use.
- Stateless: stdout by default, optional JSON and explicit file saving.
- Question lookup hides reference answers unless `--include-answer` is used.
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

## Latest source decisions

On incomplete batches: "only the ones it contains; but it should issue a
warning that the queiton-answer set is incomplete."

On selecting sets: "CLI needs to let you choose, yes; and if you are doing
batch, the quesitons all have to live iwthin the set you chose (unless you
chose \"all\")"

## Still open

Exact command names, JSON schemas, default/required set selection, handling of
duplicate answers and malformed inputs, and deterministic answer conversion
and scoring policies.
