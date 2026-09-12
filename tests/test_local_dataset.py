import json
import pytest
from typer.testing import CliRunner
from enronqa.cli import app
from enronqa.data import Dataset
from enronqa.local import import_local


def inputs(tmp_path):
    docs = tmp_path / "docs.jsonl"
    questions = tmp_path / "questions.jsonl"
    docs.write_text(
        json.dumps(
            {
                "document_id": "source1",
                "text": "The meeting is Tuesday.",
                "source": "synthetic",
            }
        )
        + "\n"
    )
    questions.write_text(
        json.dumps(
            {
                "question_id": "local-q",
                "document_id": "source1",
                "question": "When is the meeting?",
                "answer": "Tuesday",
                "alternate_answers": ["On Tuesday."],
                "split": "test",
            }
        )
        + "\n"
    )
    return questions, docs


def test_import_validate_and_judge_input_preserve_identity(tmp_path):
    questions, docs = inputs(tmp_path)
    dest = tmp_path / "dataset"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "import-dataset",
            "--questions",
            str(questions),
            "--documents",
            str(docs),
            "--data-dir",
            str(dest),
            "--dataset-id",
            "synthetic/local",
        ],
    )
    assert result.exit_code == 0, result.output
    answers = tmp_path / "answers.jsonl"
    answers.write_text('{"question_id":"local-q","answer":"Tuesday"}\n')
    result = runner.invoke(
        app, ["validate", str(answers), "--set", "test", "--data-dir", str(dest)]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["dataset"]["id"] == "synthetic/local"
    result = runner.invoke(
        app, ["judge-input", str(answers), "--set", "test", "--data-dir", str(dest)]
    )
    assert result.exit_code == 0, result.output
    packet = json.loads(result.output)
    assert packet["dataset"]["id"] != "MichaelR207/enron_qa_0922"
    assert packet["source"]["email"] == "The meeting is Tuesday."
    assert packet["reference_answers"] == ["Tuesday", "On Tuesday."]
    with Dataset(dest) as dataset:
        assert dataset.count("test") == 1
    with (dest / "index.sqlite").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        Dataset(dest)


@pytest.mark.parametrize("fault", ["duplicate", "missing_source", "overwrite"])
def test_import_failure_is_atomic(tmp_path, fault):
    questions, docs = inputs(tmp_path)
    dest = tmp_path / "dataset"
    if fault == "duplicate":
        questions.write_text(questions.read_text() * 2)
    elif fault == "missing_source":
        docs.write_text("")
    else:
        dest.mkdir()
        (dest / "keep").write_text("unchanged")
    with pytest.raises(ValueError):
        import_local(questions, docs, dest, "synthetic/local")
    if fault == "overwrite":
        assert (dest / "keep").read_text() == "unchanged"
    else:
        assert not dest.exists()
