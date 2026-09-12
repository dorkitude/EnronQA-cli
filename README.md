# EnronQA-cli

A command-line interface for using **[EnronQA](https://arxiv.org/abs/2505.00263)** in your own evaluation pipeline. EnronQA is a question-answering benchmark built from Enron emails, designed to evaluate retrieval-augmented generation over private documents (Ryan, Nivera, Xu, and Campos, 2025).

Fetch the dataset, export emails and questions, and evaluate your system's answers. Use the built-in LLM judge or pipe prepared inputs to your own judge program. Calls are stateless; you choose which files to save.

## Quick start

[Install the CLI](#installation) first if needed. `your-system` and `your-judge` below represent programs you supply.

```sh
enronqa fetch
enronqa documents export --output emails.jsonl
enronqa questions export --set test --limit 100 --seed 42 --output questions.jsonl

# Your system indexes emails.jsonl and answers the exported questions.
your-system --documents emails.jsonl < questions.jsonl > answers.jsonl
enronqa validate answers.jsonl --set test
```

Score with the built-in judge using an OpenAI-compatible endpoint:

```sh
export FIREWORKS_API_KEY="your-api-key"

# The author prefers DeepSeek Flash V4 as a judge.
enronqa score answers.jsonl --set test \
  --base-url https://api.fireworks.ai/inference/v1 \
  --model accounts/fireworks/models/deepseek-v4-flash-0731 \
  --api-key-env FIREWORKS_API_KEY \
  --output report.json
```

This example uses [DeepSeek V4 Flash on Fireworks](https://fireworks.ai/models/deepseek-ai/deepseek-v4-flash-0731). Substitute your provider's [OpenAI-compatible](https://docs.fireworks.ai/tools-sdks/openai-compatibility) base URL, model ID, and API-key environment variable.

Or pipe the same answers to an external judge—no built-in API configuration needed:

```sh
enronqa judge-input answers.jsonl --set test | your-judge > judgments.jsonl
```

## Installation

### macOS: Homebrew

```sh
brew install dorkitude/tap/enronqa-cli
```

### Ubuntu 22.04+ amd64: apt

```sh
curl -fLO https://github.com/dorkitude/EnronQA-cli/releases/download/v0.2.0/enronqa-cli_0.2.0_amd64.deb
sudo apt install ./enronqa-cli_0.2.0_amd64.deb
```

Homebrew supplies Python; the `.deb` bundles an isolated Python runtime. The `.deb` is a downloadable package, not a hosted apt repository.

### Python / uv

```sh
uv tool install 'https://github.com/dorkitude/EnronQA-cli/releases/download/v0.2.0/enronqa_cli-0.2.0-py3-none-any.whl'
```

Alternatively, use `pip install` with that wheel URL inside a Python 3.10+ virtual environment. Release assets include checksums. Every installation method requires a separate `enronqa fetch` to download the dataset.

## Commands

`SET` is `train`, `dev`, `test`, or `all`. Batch commands require `--set`; individual lookups and checks use the question ID alone. Use `-` instead of a batch filename to read stdin.

| Command | Purpose and options |
| --- | --- |
| `enronqa fetch` | Download and verify the pinned dataset, then build its local index. `--data-dir PATH` selects the cache. |
| `enronqa questions export --set SET` | Export original questions as JSONL. `--limit N --seed N` selects a reproducible sample (seed defaults to `0`). `--include-answer` adds reference answers; `--include-source` adds the source email. Both are off by default and independent. |
| `enronqa questions get ID` | Look up one question. Supports `--json`, `--include-answer`, and `--include-source`. |
| `enronqa documents export` | Stream all emails as JSONL. Use `--output FILE` for one file, or `--shard-size N --output-dir DIR` for numbered shards and a manifest with counts and checksums. |
| `enronqa documents get ID` | Look up one email by its document ID. `--json` includes its metadata. |
| `enronqa instructions` | Print the shared answer-submission instructions for use in your system prompt. Supports `--json`. Original question text is never modified. |
| `enronqa validate FILE --set SET` | Validate every submitted answer without calling a judge. Returns JSON with all detected errors and coverage warnings. |
| `enronqa judge-input FILE --set SET` | Validate answers and emit one JSONL record per question for an external judge: `question_id`, `question`, `submitted_answer`, `reference_answer`, and `source`, plus provenance and submitted metadata. |
| `enronqa score FILE --set SET` | Validate and judge a batch; return a JSON report. Supports the judge options below. |
| `enronqa check ID --answer TEXT` | Judge one answer and return JSON. Supports the same judge options. |
| `enronqa --version` | Print the installed version. |
| `enronqa COMMAND --help` | Show command usage and options. |

**Shared options:** output commands accept `--output FILE` and `--force`; stdout is the default. Dataset commands accept `--data-dir PATH`. `--json` selects structured output for lookups/instructions; validation and judging already return JSON, and exports return JSONL.

### Judge options

These apply to `score` and `check`.

| Option | Behavior |
| --- | --- |
| `--base-url URL` | OpenAI-compatible API base URL, such as `https://api.fireworks.ai/inference/v1`. Required unless `OPENAI_BASE_URL` is set. Uses Chat Completions. |
| `--model ID` | Judge model identifier. Required; no provider or model is hard-coded. |
| `--api-key-env NAME` | Read credentials from this environment variable; defaults to `OPENAI_API_KEY`. Credentials are never included in reports. |
| `--verbose` | Use an expanded built-in prompt and request a brief explanation alongside the verdict. Off by default. |
| `--judge-prompt FILE` | Replace the built-in judge instructions with your own UTF-8 prompt. The CLI still supplies the four judge inputs. Your prompt must request pure JSON; its fields are unrestricted. |
| `--retries N` | Retries after the first attempt. Default `2`: at most three attempts per question, with backoff. |
| `--max-consecutive-failures N` | Stop scheduling after this many consecutive questions exhaust their retries. Default `5`. Completed results and failures are preserved. |
| `--concurrency N` | Maximum in-flight requests. Default `1`; increase it to trade higher throughput for more requests already in flight when failures occur. |
| `--timeout SECONDS` | Request socket timeout. Default `60`; must be positive. |

`--judge-prompt` cannot be combined with `--verbose` or other flags that configure the built-in prompt. Conflicts fail during preflight. Endpoint, model, credentials, and request-handling options still work with custom prompts.

## Answers and results

Submit one JSON object per line, using IDs from question export:

```jsonl
{"question_id":"<exported-question-id>","answer":"<your answer>","latency_ms":120}
```

`answer` must be a nonblank string. Extra fields are preserved as metadata and do not overwrite CLI-owned fields. There are no reserved answer strings or special abstention rules.

The built-in judge follows [EnronQA's answer-matching method, Appendix B.6](https://arxiv.org/pdf/2505.00263#page=25): it receives the question, submitted answer, gold answer, and source email, and returns a correct/incorrect verdict. The email helps distinguish supported extra details from hallucinations. Our compact JSON response and optional explanation adapt the paper's output format; different judge models need not produce identical results.

Parsed model output lives under `judgment`. For example, a result's core fields are:

```json
{"question_id":"…","status":"ok","judgment":{"correct":true}}
```

With `--verbose`, `judgment` also contains `explanation`. With a custom prompt, `judgment` contains your model's parsed JSON without requiring a `correct` field. Custom mode does not calculate built-in accuracy.

Batch reports include per-question results, submitted answers and metadata, reference answers, source IDs, dataset revision, judge model/prompt provenance, and processing counts. Built-in accuracy is **correct / successfully judged questions**; failed and unprocessed questions are reported separately and excluded. Accuracy is `null` if no questions were successfully judged. Missing questions generate a coverage warning and are not counted as incorrect.

## Validation and failures

The CLI checks configuration, local data, and output destinations before reading a batch or making judge requests. It validates the entire batch before grading: malformed JSONL, missing/blank answers, unknown IDs, out-of-set IDs, and duplicate IDs reject the whole batch with line-numbered errors. There are no partial grades for invalid input. Invalid `judge-input` batches write their validation report to stderr and emit no JSONL; coverage warnings also go to stderr.

Transient request errors and invalid judge JSON are retried. Exhausted questions are recorded as failures and processing continues until the consecutive-failure limit is reached. The consecutive-failure count follows completion order; report results retain input order. Clear configuration errors, such as rejected credentials or an unknown model, stop processing immediately. Failed or interrupted grading returns a nonzero exit status and preserves the report of completed, failed, and unprocessed items. Ctrl-C stops scheduling and retries, waits for in-flight requests to finish or time out, then writes the report. An incorrect answer alone is not a processing error.

Existing output files require `--force` and are replaced only when output is ready. Sharded export can replace an existing directory only if its manifest accounts for all files in that directory.

## Dataset and license

The CLI fetches [the upstream dataset](https://huggingface.co/datasets/MichaelR207/enron_qa_0922) at revision `c0b3a9190fd970e83cfbe7d399a08860e43e221e`, verifies SHA-256 checksums, and indexes it locally. Other commands never download data. Allow several GB of disk space. The cache is `$XDG_CACHE_HOME/enronqa` or `~/.cache/enronqa`; override it with `ENRONQA_DATA_DIR` or `--data-dir`.

This revision contains 528,304 questions (333,473 train, 105,515 dev, 89,316 test) and 73,772 unique email paths. Splits separate questions, not necessarily emails. Document IDs are upstream paths; question IDs are stable hashes tied to the revision. Exports stream records; batch validation and reports require memory proportional to batch size.

CLI code is **MIT licensed**. The dataset has separate [licensing considerations](docs/DATASET_LICENSING.md) and is not bundled or rehosted here.

For development: `uv sync`, `uv run pytest`, `uv build`.

### Local datasets

Use an explicit local dataset when evaluating another corpus. The importer retains
its own dataset identity and a content-derived revision; it does not change the
pinned EnronQA download.

```sh
enronqa import-dataset --dataset-id example/my-qa \
  --questions questions.jsonl --documents documents.jsonl --data-dir ./my-qa
enronqa judge-input answers.jsonl --set test --data-dir ./my-qa
enronqa score answers.jsonl --set test --data-dir ./my-qa \
  --base-url https://provider.example/v1 --model MODEL
```

Each question JSONL object requires `question_id`, `document_id`, `question`, and
`answer`; optional fields are `alternate_answers` (list of strings) and `split`
(`train`, `dev`, or `test`, default `test`). Each document requires `document_id`
and `text`, with optional `source`. For compatibility with existing judge packets,
source text is exposed under `source.email` and source labels under `source.user`.
Use a custom judge prompt for a different source domain when appropriate.

The destination must be new. Import rejects duplicate IDs and missing sources,
validates records before publishing the directory, and verifies the resulting
SQLite checksum whenever it is opened. All validation and judge outputs retain
the imported dataset ID and revision.

To make judge inference settings explicit, pass `--request-options options.json`
to `score` or `check`. Supported JSON keys are `temperature`, `max_tokens`, and
`reasoning_effort`; only use options supported by your provider. For example:

```json
{"temperature": 0, "max_tokens": 1024, "reasoning_effort": "none"}
```

Reports preserve these settings and an `api_attempts` list per result, containing
elapsed seconds and provider-reported token usage. Usage is `null` when the
provider does not report it, including some failed requests. Reported usage for
incomplete or malformed completions is retained across retries. No token prices
are assumed by the CLI.
