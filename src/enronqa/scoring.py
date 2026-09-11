"""Reusable full-batch validation and lexical comparison; no model calls."""

import json
import math
import unicodedata
from datetime import datetime, timezone

from . import __version__
from .data import DATASET, REVISION


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def check_json_values(value):
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            item.encode("utf-8")  # JSON escape syntax can otherwise hide lone surrogates.
        elif isinstance(item, float) and not math.isfinite(item):
            raise ValueError("JSON numbers must be finite")
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def validation(stream, dataset, selection):
    records, errors, seen = [], [], set()
    for line_number, line in enumerate(stream, 1):

        def error(message, qid=None):
            errors.append({"line": line_number, "question_id": qid, "message": message})

        try:
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            value = json.loads(
                line,
                object_pairs_hook=json_object,
                parse_constant=lambda x: (_ for _ in ()).throw(
                    ValueError(f"Invalid JSON constant: {x}")
                ),
            )
            check_json_values(value)
        except (ValueError, RecursionError) as exc:
            error(f"Malformed JSON: {exc}")
            continue
        if not isinstance(value, dict):
            error("Record must be a JSON object")
            continue
        qid, answer = value.get("question_id"), value.get("answer")
        if not isinstance(qid, str) or not qid.strip():
            error("question_id must be a nonblank string")
        else:
            if qid in seen:
                error("Duplicate question_id", qid)
            seen.add(qid)
            question = dataset.question(qid)
            if question is None:
                error("Unknown question_id", qid)
            elif selection != "all" and question["split"] != selection:
                error(f"Question does not belong to selected set '{selection}'", qid)
        if not isinstance(answer, str) or not answer.strip():
            error(
                'answer must be a nonblank string; use "I don\'t know" to abstain',
                qid if isinstance(qid, str) else None,
            )
        records.append(value)
    if not records and not errors:
        errors.append(
            {"line": None, "question_id": None, "message": "Input batch is empty"}
        )
    total = dataset.count(selection)
    # Coverage counts only valid IDs belonging to the chosen set, once each.
    covered = sum(
        1
        for qid in seen
        if (q := dataset.question(qid)) is not None
        and (selection == "all" or q["split"] == selection)
    )
    warnings = []
    if covered < total:
        warnings.append(
            {
                "code": "incomplete_question_set",
                "message": f"Submitted {covered} of {total} questions; missing questions are not graded.",
            }
        )
    report = {
        "schema_version": "1",
        "valid": not errors,
        "dataset": {"id": DATASET, "revision": REVISION},
        "set": selection,
        "coverage": {"submitted": covered, "total": total, "missing": total - covered},
        "warnings": warnings,
        "errors": errors,
    }
    return records, report


def grade(record, question, scorer="normalized-exact"):
    transform = normalize if scorer == "normalized-exact" else lambda x: x
    abstained = normalize(record["answer"]) == "i don't know"
    references = [question["answer"], *question["alternate_answers"]]
    matched = next(
        (ref for ref in references if transform(record["answer"]) == transform(ref)),
        None,
    )
    return {
        "question_id": question["question_id"],
        "question": question["question"],
        "split": question["split"],
        "document_id": question["document_id"],
        "submitted_answer": record["answer"],
        "reference_answers": references,
        "correct": matched is not None and not abstained,
        "abstained": abstained,
        "comparison": {
            "scorer": scorer,
            "matched_reference": matched if not abstained else None,
        },
        "metadata": {
            key: value
            for key, value in record.items()
            if key not in ("question_id", "answer")
        },
    }


def score(records, validation_report, dataset, scorer="normalized-exact"):
    if scorer not in ("normalized-exact", "exact"):
        raise ValueError("Unknown scorer")
    if not validation_report["valid"]:
        raise ValueError("Cannot grade an invalid batch")
    results = [
        grade(record, dataset.question(record["question_id"]), scorer)
        for record in records
    ]
    correct = sum(item["correct"] for item in results)
    return {
        **validation_report,
        "cli_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scorer": {
            "name": scorer,
            "version": "1",
            "meaning": "Lexical agreement with upstream gold or alternate answers; not semantic correctness",
            "normalization": ["Unicode NFC", "casefold", "whitespace collapse"]
            if scorer == "normalized-exact"
            else [],
        },
        "summary": {
            "correct": correct,
            "incorrect": len(results) - correct,
            "abstained": sum(r["abstained"] for r in results),
            "denominator": len(results),
            "accuracy": correct / len(results),
        },
        "results": results,
    }
