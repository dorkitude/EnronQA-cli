# Licensing and redistribution findings

Status: findings as of 2026-09-11. Not legal advice. Nothing derived from the
dataset is redistributed by this repository until the open points below are
resolved with Kyle.

## What is pinned

- Dataset: `MichaelR207/enron_qa_0922` on Hugging Face, revision
  `c0b3a9190fd970e83cfbe7d399a08860e43e221e`, last modified 2024-09-22.
  Files: `data/{train-00000-of-00002,train-00001-of-00002,dev-00000-of-00001,test-00000-of-00001}.parquet`
  (SHA-256 sums recorded locally next to the downloads).
- Paper: Ryan, Xu, Nivera, Campos. *EnronQA: Towards Personalized RAG over
  Private Documents.* arXiv:2505.00263 (v1, 2025-05-01).

## Findings

1. **The Hugging Face dataset card declares no license.** The repository
   README contains only the auto-generated `dataset_info` block; the API
   `license` field is null. There is no LICENSE file among the repo files.
2. **The arXiv paper is CC BY 4.0.** The header of the arXiv HTML reads
   "License: CC BY 4.0". That license attaches to the paper. The paper's only
   release statement is the footnote "All data released on this Huggingface
   repo: MichaelR207/enron_qa_0922"; it does not state a dataset license.
   The paper's data section says the authors "release miscellaneous artifacts
   produced in creating the core dataset" (Mixtral verified answers, chains of
   thought), which is consistent with the `alternate_answers`,
   `incorrect_answers`, and rationale fields in the parquet files.
3. **The underlying Enron corpus has no formal license.** The CMU distribution
   page (William Cohen) says the dataset is distributed "as a resource for
   researchers who are interested in improving current email tools, or
   understanding how email is currently used" and asks users to "be sensitive
   to the privacy of the people involved". It notes that "some messages have
   been deleted as part of a redaction effort due to requests from affected
   employees". The current recommended version is the May 7, 2015 release,
   which is the version the EnronQA paper says it used. The corpus originated
   from a FERC public release during the 2003 Western Energy Markets
   investigation.
4. **The dataset's questions and answers were machine generated**
   (Llama 3.1 70B Instruct, per the paper) from the email text. The email
   text itself is the Enron corpus. Any redistribution of the `email` column
   carries the corpus's privacy caveats; the questions and answers quote
   names, amounts, and passages from those emails.

## Consequences for this project

- Scripts, aggregate counts, and category statistics: safe to publish (they
  contain no email text). This is what the repository does.
- Per-question ledgers, canonical answers, and reformulated questions: they
  quote email content. Keep local until licensing is clarified.
- A future `enronqa` CLI that ships or downloads questions: prefer
  downloading from the pinned Hugging Face revision at runtime rather than
  vendoring the data. If reformulated items are to be published, the cleanest
  route is to ask the EnronQA authors to state a dataset license (or to accept
  a derived-data contribution), and to honour the CMU privacy request by not
  exposing full email bodies.

## Open points for Kyle

- Whether to contact the EnronQA authors about an explicit dataset license.
- Whether reformulated questions (which are derived from LLM-generated
  questions over Enron text) may be published as a separate artifact, and
  under what license, once the above is answered.
