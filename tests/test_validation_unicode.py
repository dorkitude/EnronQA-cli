"""Malformed bytes and ambiguous JSON must never produce partial grades."""
import json

import pytest
from typer.testing import CliRunner

from enronqa.cli import app
from enronqa.scoring import validation


class TinyDataset:
    def __init__(self, *args):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def count(self, selection):
        return 1

    def question(self, question_id):
        if question_id == "q1":
            return {"question_id": "q1", "split": "test", "document_id": "d1",
                    "question": "Approved?", "answer": "yes", "alternate_answers": []}


@pytest.mark.parametrize("bad", [
    b'\xff',
    b'{"question_id":"q1","answer":"\\ud800"}',
    b'{"question_id":"q1","answer":"yes","metadata":{"\\udfff":1}}',
    b'{"question_id":"missing","question_id":"q1","answer":"yes"}',
    b'{"question_id":"q1","answer":"no","answer":"yes"}',
    b'{"question_id":"q1","answer":"yes","metadata":{"x":1,"x":2}}',
    b'{"question_id":"q1","answer":"yes","latency":1e999}',
    b'[' * 2000 + b']' * 2000,
])
def test_reject_bad_record_and_continue(bad):
    _, report = validation([bad, b'not json', b'{"question_id":"q1","answer":"yes"}'], TinyDataset(), "test")
    assert not report["valid"]
    assert [error["line"] for error in report["errors"]] == [1, 2]
    assert report["coverage"]["submitted"] == 1
    json.dumps(report, ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize("stdin", [False, True])
def test_invalid_utf8_cli_has_full_json_errors(tmp_path, monkeypatch, stdin):
    monkeypatch.setattr("enronqa.cli.Dataset", TinyDataset)
    data = b'{"question_id":"q1","answer":"yes"}\n\xff\nnot json\n'
    path = tmp_path / "answers.jsonl"
    path.write_bytes(data)
    result = CliRunner().invoke(app, ["score", "-" if stdin else str(path), "--set", "test"], input=data if stdin else None)
    assert result.exit_code == 2
    report = json.loads(result.stdout)
    assert [error["line"] for error in report["errors"]] == [2, 3]
    assert "results" not in report and "summary" not in report
