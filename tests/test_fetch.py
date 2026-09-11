import io
import sqlite3

import pytest

from enronqa import data


def test_fetch_verified_reused_and_failure_preserves_index(tmp_path, monkeypatch):
    payload = b"synthetic parquet substitute"
    import hashlib

    expected = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(data, "FILES", {"test.parquet": expected})
    calls = []

    def download(*args, **kwargs):
        calls.append(args)
        return io.BytesIO(payload)

    monkeypatch.setattr(data.urllib.request, "urlopen", download)

    def build(raw, target):
        db = sqlite3.connect(target)
        db.executescript(
            "CREATE TABLE metadata(key TEXT,value TEXT); CREATE TABLE documents(document_id TEXT,email TEXT,user TEXT); CREATE TABLE questions(question_id TEXT,split TEXT,document_id TEXT,question TEXT,answer TEXT,alternates TEXT);"
        )
        db.executemany(
            "INSERT INTO metadata VALUES (?,?)",
            [("revision", data.REVISION), ("schema", "1")],
        )
        db.commit()
        db.close()

    monkeypatch.setattr(data, "build_index", build)
    assert data.fetch(tmp_path)["documents"] == 0
    assert len(calls) == 1
    data.fetch(tmp_path)
    assert len(calls) == 1
    index = tmp_path / data.REVISION / "index.sqlite"
    original = index.read_bytes()
    (tmp_path / data.REVISION / "raw" / "test.parquet").write_bytes(b"bad")
    monkeypatch.setattr(
        data.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"corrupt")
    )
    with pytest.raises(ValueError, match="Checksum"):
        data.fetch(tmp_path)
    assert index.read_bytes() == original
    assert not list((tmp_path / data.REVISION / "raw").glob(".download-*"))


def test_fetch_index_build_failure_not_published(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "FILES", {})

    def fail(raw, target):
        raise RuntimeError("bad schema")

    monkeypatch.setattr(data, "build_index", fail)
    with pytest.raises(RuntimeError):
        data.fetch(tmp_path)
    assert not (tmp_path / data.REVISION / "index.sqlite").exists()
    assert not list((tmp_path / data.REVISION).glob(".index-*"))
