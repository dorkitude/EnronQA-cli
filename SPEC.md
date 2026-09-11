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

## Illustrative command surface (not yet agreed)

```sh
enronqa score answers.jsonl
enronqa question get <question-id>
enronqa answer check <question-id> --answer '...'
```

Command names, JSONL schema, output flags, and other question metadata remain undecided. Batch and granular interfaces do not imply that the CLI launches a user's system or calls HTTP endpoints.

## Evaluation design under investigation

An audit of the EnronQA questions is assessing faithful reformulations that permit deterministic answer evaluation. Exact matching, normalization, structured answers, and multiple-choice transformations remain proposals, not accepted scoring requirements. Deterministic scoring alone does not establish reliable gold labels.

## Decision context

Kyle requested a public MIT Go/Cobra CLI and asked to workshop its specification before implementation. For the interface, Kyle clarified: "there shoudl be a batch format for passing a JSONL file into it. or there should be a call-as-needed set of more granular functions."

On whether individual checks should accumulate into named runs, Kyle chose: "stateless, just stdout (with json as an option and saving as another option)".

Kyle confirmed question-only retrieval by default, with `--include-answer` to reveal the reference answer.
