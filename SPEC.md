# EnronQA-cli specification

The README defines the intended interface from the September 11, 2026
README-first workshop. Implementation work is tracked in
[LLM judging #4](https://github.com/dorkitude/EnronQA-cli/issues/4) and
[external judge inputs #5](https://github.com/dorkitude/EnronQA-cli/issues/5).
The v0.1.0 release predates this judge-based design; do not treat these issues
as implemented until their acceptance criteria pass.

## Confirmed behavior

- Python 3.10+, Typer, public MIT-licensed tool. Explicit pinned dataset fetch;
  no implicit downloads, named runs, or hidden evaluation history.
- Original question wording and stable IDs; answers and source emails hidden
  from question lookup/export unless independently requested.
- Required `--set train|dev|test|all` for batches and question export. Full-batch
  validation precedes work; collect all input errors and reject invalid batches.
- Score submitted questions only. Missing coverage is a warning. Judge failures
  and unprocessed items are distinct from incorrect answers and excluded from
  built-in accuracy. With no successful judgments, accuracy is null.
- No reserved answer strings, abstention flags, or special abstention accounting.
  Every nonblank answer is sent through the configured judge.
- Built-in judging follows EnronQA Appendix B.6's question, submitted answer,
  gold answer, and source-email inputs. Minimal boolean JSON by default;
  `--verbose` requests an expanded prompt and an explanation.
- `--judge-prompt FILE` replaces the judge instructions. Custom prompts must
  request pure JSON; no correctness schema is imposed on their response.
  Parsed content goes under `judgment` and cannot overwrite CLI-owned fields.
  Custom mode does not compute built-in accuracy.
- Prompt overrides conflict with built-in prompt-configuration flags, including
  `--verbose`. Fail in preflight. API/model and request-handling options remain
  usable with overrides.
- Configurable OpenAI-compatible Chat Completions base URL, model, and API-key
  environment variable. No fixed provider. Fireworks DeepSeek V4 Flash is the
  author's example preference, not a claimed reproduction of paper results.
- Two retries after the initial attempt, then record the failed question and
  continue. Stop scheduling after five consecutive exhausted questions; retain
  completed/failure/unprocessed reporting. Clearly identified configuration
  errors stop processing immediately. Thresholds and concurrency are flags.
- `judge-input` emits validated JSONL for arbitrary external judge programs,
  without requiring the built-in API client configuration.
- Stdout by default, explicit saving, early output checks, and guarded overwrite
  with `--force`. Optional corpus shards include a count/checksum manifest.

## Documentation

Cite and explain EnronQA early. Show short usage examples for both judge paths
before installation, with a link to installation in the usage prelude. Include
full command and option tables. Describe the intended interface without
"upcoming" labels; record implementation gaps in GitHub issues.

## Repository scope

Keep runtime code, product tests, packaging, user documentation, and interface
specifications here. Research experiments and question-reformulation audits live
in a separate research workspace.
