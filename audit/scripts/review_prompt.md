You are auditing question-answer items from the EnronQA benchmark. Each item is a natural-language question about one email, with a gold answer written as a full sentence, one alternate phrasing of the gold answer, and two incorrect answers. The research question: can this item be reformulated so that a system's answer can be scored DETERMINISTICALLY (no LLM judge) while preserving the same information need?

For each item, decide the tightest faithful answer schema and produce a canonical short answer that a deterministic scorer could compare against after normalization.

Schema categories (cat):
- bool            yes/no question with an unambiguous truth value in the email
- date            a calendar date (normalize to YYYY-MM-DD; use partial like 2001-11 or --12-08 if year absent)
- time            a clock time (HH:MM 24h)
- datetime        date and time together
- number          a plain count or quantity (canon = digits, optionally with unit, e.g. "3", "250 MW")
- money           currency amount (canon like "USD 107.45", "USD 5.1e9" ok as "USD 5100000000")
- percent         a percentage (canon like "12.5%")
- duration        a length of time (canon like "P3D", "2 weeks")
- person          a named person (canon = full name as in email; list aliases if the email uses variants)
- org             a company, agency, or group name
- place           a location
- email_addr      an email address
- entity          another named thing: document title, subject line, product, deal name, transaction id, phone number, URL
- list            an explicit set of items (canon = JSON array; say ordered:true only if order is part of the information need)
- multi_field     a fixed set of named fields, e.g. {"person":"...", "role":"..."} (canon = JSON object; only when each field alone is deterministic)
- span            the answer is a specific quoted or near-verbatim passage from the email and only that passage answers it (canon = the exact span text)
- free_text       the information need is inherently explanatory, causal, summarizing, or interpretive ("why", "main topic", "what is the purpose", "what action is asked") and no short canonical form preserves it

Verdict:
- convertible          canonical answer fully preserves the information need; a deterministic comparison against canon (+aliases) is fair
- convertible_rewrite  convertible only if the QUESTION is rewritten to pin the expected form (give the rewritten question in "rq")
- unconvertible        no faithful deterministic form; would need an LLM judge or a task change (e.g. multiple choice)

Flags (include any that apply):
- gold_unsupported   the gold answer is not supported by the email text
- gold_wrong         the email contradicts the gold answer
- ambiguous_question the question admits several distinct correct answers from the email
- vague_gold         gold is hedged or vague ("soon after Monday night", "not smooth")
- answer_in_question the question text already contains the answer
- normalization_risk canon has multiple defensible surface forms that simple normalization would not unify (nicknames, partial names, abbreviations, rounding)
- multi_valid_alias  the email itself uses several forms for the answer (list them in "aliases")
- mcq_leak_hedge     an incorrect answer says the info is unavailable/cannot be determined (signals the gold exists)
- mcq_leak_anachron  an incorrect answer contains a year after 2002 or otherwise obviously non-Enron-era content
- mcq_leak_style     incorrect answers are trivially distinguishable by length/style/genericness
- mcq_incorrect_actually_correct  an incorrect answer is actually acceptable given the email
- boilerplate        the question targets disclaimer/signature/list-server boilerplate rather than the email's content

Confidence (conf): high | medium | low, about your own classification.

Output: ONLY a JSON array, one object per item in input order, each with keys:
{"i": <item index>, "cat": ..., "verdict": ..., "canon": <string|array|object>, "aliases": [..] (optional), "rq": <rewritten question> (only for convertible_rewrite), "flags": [...], "conf": ..., "note": <at most 12 words, optional>}
Do not include any text outside the JSON array. Do not quote long email passages.
