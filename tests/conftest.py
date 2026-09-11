import sqlite3

import pytest

from enronqa.data import REVISION


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
