"""Stateless command interface."""

import json
import random
import shutil
import sys
import tempfile
from contextlib import contextmanager
from enum import Enum
from pathlib import Path

import typer

from . import __version__
from .data import DATASET, REVISION, Dataset, default_dir, digest
from .data import fetch as fetch_data
from .output import output, preflight
from .scoring import score as score_batch
from .scoring import validation

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
questions = typer.Typer(no_args_is_help=True)
documents = typer.Typer(no_args_is_help=True)
app.add_typer(questions, name="questions")
app.add_typer(documents, name="documents")


class Selection(str, Enum):
    train = "train"
    dev = "dev"
    test = "test"
    all = "all"


class Scorer(str, Enum):
    normalized = "normalized-exact"
    exact = "exact"


@contextmanager
def errors():
    try:
        yield
    except (ValueError, OSError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2)


def emit(value, destination=None, force=False, as_json=True):
    with output(destination, force) as stream:
        stream.write(
            (json.dumps(value, ensure_ascii=False, indent=2) if as_json else str(value))
            + "\n"
        )


def public_question(question, dataset, include_answer=False, include_source=False):
    result = {
        k: v
        for k, v in question.items()
        if k not in ("answer", "alternate_answers", "document_id")
    }
    if include_answer:
        result.update(
            answer=question["answer"],
            alternate_answers=question["alternate_answers"],
            document_id=question["document_id"],
        )
    if include_source:
        result["source"] = dataset.document(question["document_id"])
    return result


@app.callback(invoke_without_command=True)
def main(version: bool = typer.Option(False, "--version", is_eager=True)):
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@app.command()
def fetch(data_dir: Path | None = typer.Option(None, "--data-dir")):
    """Explicitly download, verify, and index the pinned upstream dataset."""
    with errors():
        try:
            counts = fetch_data(
                data_dir or default_dir(), lambda m: typer.echo(m, err=True)
            )
        except Exception as exc:
            raise ValueError(
                f"Fetch failed: {exc}. Check network access and free disk space, then retry enronqa fetch with the same --data-dir."
            ) from exc
        emit({"dataset": DATASET, "revision": REVISION, "counts": counts})


@questions.command("get")
def question_get(
    question_id: str,
    include_answer: bool = False,
    include_source: bool = False,
    json_output: bool = typer.Option(False, "--json"),
    output_path: Path | None = typer.Option(None, "--output"),
    force: bool = False,
    data_dir: Path | None = None,
):
    """Look up an unchanged upstream question; answers and source are opt-in."""
    with errors():
        preflight(output_path, force)
        with Dataset(data_dir) as dataset:
            question = dataset.question(question_id)
            if question is None:
                raise ValueError(f"Unknown question ID: {question_id}")
            result = public_question(question, dataset, include_answer, include_source)
            emit(
                result
                if json_output or include_source or include_answer
                else result["question"],
                output_path,
                force,
                json_output or include_source or include_answer,
            )


@questions.command("export")
def question_export(
    selection: Selection = typer.Option(..., "--set"),
    include_answer: bool = False,
    include_source: bool = False,
    limit: int | None = typer.Option(None, min=1),
    seed: int = 0,
    output_path: Path | None = typer.Option(None, "--output"),
    force: bool = False,
    data_dir: Path | None = None,
):
    """Export questions as JSONL; --limit uses reproducible sampling with --seed."""
    with errors():
        preflight(output_path, force)
        with Dataset(data_dir) as dataset:
            total = dataset.count(selection.value)
            if limit is not None and limit > total:
                raise ValueError(f"--limit exceeds selected set size ({total})")
            selected = (
                set(random.Random(seed).sample(range(total), limit))
                if limit is not None
                else None
            )
            with output(output_path, force) as stream:
                for i, question in enumerate(dataset.questions(selection.value)):
                    if selected is None or i in selected:
                        stream.write(
                            json.dumps(
                                public_question(
                                    question, dataset, include_answer, include_source
                                ),
                                ensure_ascii=False,
                            )
                            + "\n"
                        )


@documents.command("get")
def document_get(
    document_id: str,
    json_output: bool = typer.Option(False, "--json"),
    output_path: Path | None = typer.Option(None, "--output"),
    force: bool = False,
    data_dir: Path | None = None,
):
    """Look up an email by its stable upstream path ID."""
    with errors():
        preflight(output_path, force)
        with Dataset(data_dir) as dataset:
            value = dataset.document(document_id)
            if value is None:
                raise ValueError(f"Unknown document ID: {document_id}")
            emit(
                value if json_output else value["email"],
                output_path,
                force,
                json_output,
            )


@documents.command("export")
def document_export(
    output_path: Path | None = typer.Option(None, "--output"),
    force: bool = False,
    shard_size: int | None = typer.Option(None, min=1),
    output_dir: Path | None = None,
    data_dir: Path | None = None,
):
    """Stream all unique emails as JSONL, optionally into numbered shards."""
    with errors():
        if bool(shard_size) != bool(output_dir) or (output_dir and output_path):
            raise ValueError("Use --shard-size with --output-dir, without --output")
        preflight(output_path, force)
        preflight(output_dir, force, directory=True)
        with Dataset(data_dir) as dataset:
            if output_dir is None:
                with output(output_path, force) as stream:
                    for document in dataset.documents():
                        stream.write(json.dumps(document, ensure_ascii=False) + "\n")
                return
            stage = Path(
                tempfile.mkdtemp(prefix=".enronqa-shards-", dir=output_dir.parent)
            )
            try:
                manifest = {
                    "schema_version": "1",
                    "dataset": DATASET,
                    "revision": REVISION,
                    "shards": [],
                    "documents": 0,
                }
                stream = None
                try:
                    for i, document in enumerate(dataset.documents()):
                        if i % shard_size == 0:
                            if stream:
                                stream.close()
                            name = f"emails-{i // shard_size:05d}.jsonl"
                            stream = (stage / name).open("w", encoding="utf-8")
                            manifest["shards"].append({"file": name, "count": 0})
                        stream.write(json.dumps(document, ensure_ascii=False) + "\n")
                        manifest["shards"][-1]["count"] += 1
                        manifest["documents"] += 1
                finally:
                    if stream:
                        stream.close()
                for shard in manifest["shards"]:
                    shard["sha256"] = digest(stage / shard["file"])
                (stage / "manifest.json").write_text(
                    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
                )
                # Recheck at publication and preserve an old export until success.
                preflight(output_dir, force, directory=True)
                backup = None
                if output_dir.exists():
                    backup = Path(
                        tempfile.mkdtemp(
                            prefix=".enronqa-backup-", dir=output_dir.parent
                        )
                    )
                    backup.rmdir()
                    output_dir.rename(backup)
                created = False
                try:
                    output_dir.mkdir()  # exclusive: a concurrent writer is never overwritten
                    created = True
                    for path in stage.iterdir():
                        path.rename(output_dir / path.name)
                except BaseException:
                    if created:
                        shutil.rmtree(output_dir)
                    if backup is not None and not output_dir.exists():
                        backup.rename(output_dir)
                    raise
                else:
                    if backup is not None:
                        shutil.rmtree(backup)
            finally:
                shutil.rmtree(stage, ignore_errors=True)


INSTRUCTIONS = """EnronQA-cli answer conventions (not upstream EnronQA instructions):
Return one JSON object per question, with question_id and a nonblank string answer.
Use the concise answer you judge correct. Put reasoning in a separate optional field.
Use the exact string \"I don't know\" to abstain; abstentions count as incorrect.
The default scorer compares against upstream gold and alternate answers after Unicode
NFC normalization, case folding, and whitespace collapse. It preserves punctuation,
numbers, and negation. Valid paraphrases can fail: this measures lexical agreement,
not semantic correctness. No answer-format instructions are added to questions.
"""


@app.command()
def instructions(
    json_output: bool = typer.Option(False, "--json"),
    output_path: Path | None = typer.Option(None, "--output"),
    force: bool = False,
):
    """Print shared answer conventions for use in an experiment's system prompt."""
    with errors():
        preflight(output_path, force)
        emit(
            {"source": "EnronQA-cli", "instructions": INSTRUCTIONS}
            if json_output
            else INSTRUCTIONS.rstrip(),
            output_path,
            force,
            json_output,
        )


def batch(input_path, selection, output_path, force, data_dir, scorer=None):
    with errors():
        preflight(output_path, force)
        with Dataset(data_dir) as dataset:
            if input_path == "-":
                records, report = validation(
                    getattr(sys.stdin, "buffer", sys.stdin), dataset, selection
                )
            else:
                with open(input_path, "rb") as stream:
                    records, report = validation(stream, dataset, selection)
            if report["valid"] and scorer is not None:
                report = score_batch(records, report, dataset, scorer)
            emit(report, output_path, force)
            if not report["valid"]:
                raise typer.Exit(2)


@app.command()
def validate(
    input_path: str,
    selection: Selection = typer.Option(..., "--set"),
    output_path: Path | None = typer.Option(None, "--output"),
    force: bool = False,
    json_output: bool = typer.Option(False, "--json"),
    data_dir: Path | None = None,
):
    """Validate every JSONL record before grading; '-' reads stdin. Always JSON."""
    batch(input_path, selection.value, output_path, force, data_dir)


@app.command()
def score(
    input_path: str,
    selection: Selection = typer.Option(..., "--set"),
    output_path: Path | None = typer.Option(None, "--output"),
    force: bool = False,
    scorer: Scorer = Scorer.normalized,
    json_output: bool = typer.Option(False, "--json"),
    data_dir: Path | None = None,
):
    """Validate then grade a JSONL batch. Accuracy is lexical, not semantic."""
    batch(input_path, selection.value, output_path, force, data_dir, scorer.value)


@app.command()
def check(
    question_id: str,
    answer: str = typer.Option(...),
    scorer: Scorer = Scorer.normalized,
    output_path: Path | None = typer.Option(None, "--output"),
    force: bool = False,
    json_output: bool = typer.Option(False, "--json"),
    data_dir: Path | None = None,
):
    """Check one answer without storing a run. Returns a JSON report."""
    with errors():
        preflight(output_path, force)
        with Dataset(data_dir) as dataset:
            records, report = validation(
                [json.dumps({"question_id": question_id, "answer": answer})],
                dataset,
                "all",
            )
            if report["valid"]:
                report = score_batch(records, report, dataset, scorer.value)
            # Single checks have no batch-completeness expectation.
            report.pop("coverage")
            report["warnings"] = []
            emit(report, output_path, force)
            if not report["valid"]:
                raise typer.Exit(2)
