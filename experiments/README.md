# Released CLI usefulness trial — September 11, 2026

The v0.1.0 CLI is useful for reproducible dataset access and experiment plumbing.
Its lexical answer score is not sufficient to assess general QA correctness or
word sense induction. Follow-up: [issue #3](https://github.com/dorkitude/EnronQA-cli/issues/3).

## What was actually run

Used the installed release wheel, not an editable checkout. Reused the previously
verified pinned dataset cache; this trial did not repeat a fresh network download.
Exported all 73,772 emails and 100 test questions with `--limit 100 --seed 20260911`.
Built a SQLite FTS5 index from the exported JSONL. For each question, OR-combined
up to 32 distinct non-stopword tokens and retrieved ten emails ranked by FTS5
BM25. The baseline answer was the sentence/line from the highest-ranked email
with the greatest question-token overlap. It used no reference answers.

Separately, the assistant answered the first ten sampled questions in export
order with their source emails visible via `questions get --include-source`.
Reference answers were hidden until those answers were written and graded.
This separates the answer scorer's behavior from retrieval failures. It is a
small assistant-reviewed diagnostic, not independent human adjudication.

After predictions were fixed, exported the same sample with `--include-answer`
and calculated exact-source retrieval metrics outside the CLI.

| Measurement | Observed result |
| --- | ---: |
| Source email at rank 1 | 63/100 |
| Source email within top 5 | 86/100 |
| Source email within top 10 | 89/100 |
| MRR@10, misses count as zero | 0.7242 |
| Naive retrieved-sentence lexical accuracy | 0/100 |
| Source-visible assistant answers: lexical accuracy | 1/10 |
| Full-corpus FTS indexing | 5.06 seconds |
| Retrieval + extraction for 100 questions | 12.65 seconds |
| FTS index file | 311,894,016 bytes |

Timing is one run on the development VM, not a performance guarantee. Retrieval
metrics credit only the designated source path. Duplicate emails, quoted
threads, or other sufficient evidence are not credited; this is not exhaustive
relevance judgment. No embedding fine-tuning or sense-induction model was tested.

## What the experience exposed

**Dataset access worked well.** JSONL streamed into a standard-library search
index without extra dataset-specific parsing. Stable IDs connected questions,
predictions and evidence. Sampling was repeatable. Validation and scoring
accepted the generated batch, preserved retrieval IDs as metadata, and warned
that the 100 submitted questions did not cover the entire test set, as designed.

**Lexical accuracy substantially penalized natural answers.** The ten-question
source-visible exercise produced clear substantive matches that the scorer
rejected. For the ARTO readiness question, the assistant answered "Within 90 days
of FERC approval." The reference requires a longer sentence restating ARTO,
its structure, and National Grid; the key duration is the same. For the course
cancellation question, the assistant stated that cancellation must arrive at
least three business days before class. The reference expresses the same
condition with different wording and the numeral 3. Both were rejected. An
answer naming the Microsoft deal matched and passed.

These examples demonstrate false negatives; 1/10 should not be read as an
independently established 10% semantic accuracy. The naive extractor's 0/100
also mixes genuine extraction failures with lexical mismatches; this trial does
not attribute every failure to the scorer.

The prior release check accepting 89,316 supplied gold answers verified that the
implementation matches its own reference key. It did not validate the score as
a measure of useful answering. The CLI's instructions encourage concise answers,
while many keys are full sentences, making this mismatch especially easy to hit.

**Retrieval evaluation needed custom code.** The CLI exports the necessary IDs,
but does not accept a ranked retrieval list and produce recall/MRR reports.
That missing interface matters for comparing a WSI-enhanced retriever against
an ordinary keyword or embedding baseline.

**WSI remains a separate research design problem.** This trial used QA/evidence
labels, not sense labels. A useful next experiment needs an ambiguity-focused,
reviewed evaluation set and a way to distinguish retrieval improvements from
answer-wording effects. The current CLI score alone cannot establish better
sense induction.

## Reproduction

Install v0.1.0 as in the project README, explicitly fetch the dataset, and choose
a new local work directory. All question/email/answer artifacts should stay
local. Example (set ENRONQA_DATA_DIR if using a nondefault cache):

```sh
mkdir /tmp/enronqa-trial
enronqa questions export --set test --limit 100 --seed 20260911 --output /tmp/enronqa-trial/questions.jsonl
enronqa documents export --output /tmp/enronqa-trial/emails.jsonl
uv run --no-project python experiments/released_cli_trial.py /tmp/enronqa-trial
enronqa validate /tmp/enronqa-trial/answers.jsonl --set test
enronqa score /tmp/enronqa-trial/answers.jsonl --set test --output /tmp/enronqa-trial/baseline-report.json
# Only after retrieval and answer generation:
enronqa questions export --set test --limit 100 --seed 20260911 --include-answer --output /tmp/enronqa-trial/answer-key.jsonl
```

For the manual diagnostic, independently answer the first ten question records
using `questions get ID --include-source` without `--include-answer`, write a
normal submission batch, and grade it to `manual-report.json` in the work
directory. Then run:

```sh
uv run --no-project python experiments/trial_metrics.py /tmp/enronqa-trial
```

Retrieval is reproducible with the same SQLite/tokenizer behavior and data;
manual answer wording is not an automated reproducible model run. Full local
artifacts from this trial are at `/tmp/enronqa-usefulness/`. Only scripts and
aggregate findings are committed, without emails or answer-key exports.
