import hashlib
import json
import sqlite3

import pytest
from typer.testing import CliRunner

from enronqa.cli import app
from enronqa.data import FILES, REVISION, Dataset, build_index
from enronqa.output import output
from enronqa.scoring import normalize

runner = CliRunner()


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    root = tmp_path / "cache"
    dest = root / REVISION / "index.sqlite"
    dest.parent.mkdir(parents=True)
    db = sqlite3.connect(dest)
    db.executescript("""CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
    INSERT INTO metadata VALUES ('schema','1');
    CREATE TABLE documents(document_id TEXT PRIMARY KEY,email TEXT,user TEXT);
    CREATE TABLE questions(question_id TEXT PRIMARY KEY,split TEXT,document_id TEXT,question TEXT,answer TEXT,alternates TEXT);
    """)
    db.execute("INSERT INTO metadata VALUES (?,?)", ("revision", REVISION))
    db.executemany(
        "INSERT INTO documents VALUES (?,?,?)",
        [
            ("d1", "Synthetic email one", "a"),
            ("d2", "Synthetic email two", "b"),
            ("d3", "Synthetic email three", "a"),
        ],
    )
    db.executemany(
        "INSERT INTO questions VALUES (?,?,?,?,?,?)",
        [
            ("q1", "test", "d1", "Was it approved?", "approved", '["yes"]'),
            ("q2", "test", "d2", "How much?", "$5", "[]"),
            ("q3", "train", "d3", "Who?", "Chef", "[]"),
        ],
    )
    db.commit()
    db.close()
    monkeypatch.setenv("ENRONQA_DATA_DIR", str(root))
    return root


def invoke(args, data=None):
    result = runner.invoke(app, args, input=data)
    return result


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["fetch"],
        ["questions"],
        ["questions", "get"],
        ["questions", "export"],
        ["documents"],
        ["documents", "get"],
        ["documents", "export"],
        ["score"],
        ["check"],
        ["validate"],
        ["instructions"],
    ],
)
def test_help(args):
    assert invoke(args + ["--help"]).exit_code == 0


def test_version():
    assert invoke(["--version"]).stdout.strip() == "0.1.0"


def test_missing_data(tmp_path, monkeypatch):
    monkeypatch.setenv("ENRONQA_DATA_DIR", str(tmp_path))
    r = invoke(["questions", "get", "x"])
    assert r.exit_code == 2 and "enronqa fetch" in r.stderr


def test_question_clean(corpus):
    q = json.loads(invoke(["questions", "get", "q1", "--json"]).stdout)
    assert q == {"question_id": "q1", "split": "test", "question": "Was it approved?"}
    q = json.loads(
        invoke(["questions", "get", "q1", "--json", "--include-source"]).stdout
    )
    assert q["source"]["email"] == "Synthetic email one" and "answer" not in q
    q = json.loads(invoke(["questions", "get", "q1", "--include-answer"]).stdout)
    assert q["answer"] == "approved" and "source" not in q


def test_export_sample(corpus):
    args = ["questions", "export", "--set", "test", "--limit", "1", "--seed", "42"]
    assert invoke(args).stdout == invoke(args).stdout
    assert len(invoke(args).stdout.splitlines()) == 1
    assert (
        invoke(["questions", "export", "--set", "test", "--limit", "3"]).exit_code == 2
    )


def test_score(corpus):
    r = invoke(
        ["score", "-", "--set", "test"],
        "\n".join(
            [
                json.dumps(
                    {
                        "question_id": "q1",
                        "answer": " YES ",
                        "correct": "metadata",
                        "reasoning": "why",
                    }
                ),
                json.dumps({"question_id": "q2", "answer": "I don't know"}),
            ]
        ),
    )
    assert r.exit_code == 0, r.output
    report = json.loads(r.stdout)
    assert report["summary"] == {
        "correct": 1,
        "incorrect": 1,
        "abstained": 1,
        "denominator": 2,
        "accuracy": 0.5,
    }
    assert report["results"][0]["metadata"] == {
        "correct": "metadata",
        "reasoning": "why",
    }
    assert report["warnings"] == []
    assert report["dataset"]["revision"] == REVISION


@pytest.mark.parametrize(
    "answer", ["not approved", "approved or denied", "APPROVED!", "it was approved"]
)
def test_no_substring(corpus, answer):
    result = json.loads(invoke(["check", "q1", "--answer", answer]).stdout)
    assert result["summary"]["accuracy"] == 0


@pytest.mark.parametrize("answer", ["5", "$50", "-$5"])
def test_numeric_punctuation(corpus, answer):
    assert (
        json.loads(invoke(["check", "q2", "--answer", answer]).stdout)["summary"][
            "accuracy"
        ]
        == 0
    )


def test_normalize():
    assert normalize(" E\u0301  FOO\n") == "é foo"


def test_exact(corpus):
    assert (
        json.loads(
            invoke(["check", "q1", "--answer", "APPROVED", "--scorer", "exact"]).stdout
        )["summary"]["accuracy"]
        == 0
    )


def test_validation_all_errors(corpus):
    data = 'not json\n[]\n{"question_id":"q1","answer":"yes"}\n{"question_id":"q1","answer":""}\n{"question_id":"q3"}\n{"question_id":"missing","answer":5}\n'
    r = invoke(["score", "-", "--set", "test"], data)
    assert r.exit_code == 2
    report = json.loads(r.stdout)
    assert len(report["errors"]) == 8
    assert {e["line"] for e in report["errors"]} == {1, 2, 4, 5, 6}
    assert "results" not in report and "summary" not in report


def test_coverage(corpus):
    report = json.loads(
        invoke(
            ["score", "-", "--set", "test"], '{"question_id":"q1","answer":"yes"}'
        ).stdout
    )
    assert report["summary"]["accuracy"] == 1
    assert report["coverage"] == {"submitted": 1, "total": 2, "missing": 1}
    assert report["warnings"][0]["code"] == "incomplete_question_set"


def test_all(corpus):
    assert (
        invoke(
            ["validate", "-", "--set", "all"], '{"question_id":"q3","answer":"Chef"}'
        ).exit_code
        == 0
    )


@pytest.mark.parametrize(
    "data",
    [
        "",
        "\n",
        '{"question_id":"q1","answer":null}',
        '{"question_id":"q1","answer":"yes","x":NaN}',
    ],
)
def test_invalid(corpus, data):
    assert invoke(["validate", "-", "--set", "test"], data).exit_code == 2


def test_requires_set(corpus):
    assert invoke(["score", "-"]).exit_code == 2


def test_preflight_before_input(corpus, tmp_path, monkeypatch):
    path = tmp_path / "exists"
    path.write_text("keep")

    def fail(*a, **k):
        raise AssertionError("must not open dataset")

    monkeypatch.setattr("enronqa.cli.Dataset", fail)
    r = invoke(["score", "-", "--set", "test", "--output", str(path)])
    assert r.exit_code == 2 and "already exists" in r.stderr
    assert path.read_text() == "keep"


def test_force_atomic(tmp_path):
    path = tmp_path / "file"
    path.write_text("original")
    with pytest.raises(RuntimeError), output(path, True) as out:
        out.write("new")
        raise RuntimeError()
    assert path.read_text() == "original"
    with pytest.raises(FileExistsError), output(path) as out:
        out.write("new")
    with output(path, True) as out:
        out.write("new")
    assert path.read_text() == "new"


def test_shards(corpus, tmp_path):
    dest = tmp_path / "shards"
    r = invoke(["documents", "export", "--shard-size", "2", "--output-dir", str(dest)])
    assert r.exit_code == 0, r.output
    manifest = json.loads((dest / "manifest.json").read_text())
    assert manifest["documents"] == 3
    assert [s["count"] for s in manifest["shards"]] == [2, 1]
    for shard in manifest["shards"]:
        assert (
            hashlib.sha256((dest / shard["file"]).read_bytes()).hexdigest()
            == shard["sha256"]
        )
    assert (
        invoke(
            ["documents", "export", "--shard-size", "2", "--output-dir", str(dest)]
        ).exit_code
        == 2
    )


def test_document(corpus):
    assert (
        json.loads(invoke(["documents", "get", "d1", "--json"]).stdout)["email"]
        == "Synthetic email one"
    )
    assert len(invoke(["documents", "export"]).stdout.splitlines()) == 3
    assert invoke(["documents", "get", "bad"]).exit_code == 2


def test_instructions():
    assert "not upstream" in invoke(["instructions"]).stdout
    assert (
        json.loads(invoke(["instructions", "--json"]).stdout)["source"] == "EnronQA-cli"
    )


def test_ingestion(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    for name in FILES:
        row = {
            "path": "document",
            "email": "Synthetic only",
            "user": "a",
            "questions": ["Question?"],
            "gold_answers": ["Answer"],
            "alternate_answers": [["Alternative"]],
        }
        if name.endswith("00001-of-00002.parquet"):
            row["path"] = "document2"
        pq.write_table(pa.Table.from_pylist([row]), tmp_path / name)
    root = tmp_path / "cache"
    target = root / REVISION / "index.sqlite"
    target.parent.mkdir(parents=True)
    build_index(tmp_path, target)
    with Dataset(root) as dataset:
        assert dataset.count("all") == 4
        assert dataset.counts()["documents"] == 2
        q = next(dataset.questions("test"))
        assert len(q["question_id"]) == 64 and "/" not in q["question_id"]
        assert q["alternate_answers"] == ["Alternative"]


def test_force_shards(corpus, tmp_path):
    dest = tmp_path / "shards"
    args = ["documents", "export", "--shard-size", "2", "--output-dir", str(dest)]
    assert invoke(args).exit_code == 0
    assert invoke(args + ["--force"]).exit_code == 0
    (dest / "unrelated.txt").write_text("keep")
    result = invoke(args + ["--force"])
    assert result.exit_code == 2
    assert (dest / "unrelated.txt").read_text() == "keep"


def test_corrupt_index(corpus):
    (corpus / REVISION / "index.sqlite").write_bytes(b"broken")
    result = invoke(["questions", "get", "q1"])
    assert result.exit_code == 2 and "enronqa fetch" in result.stderr
