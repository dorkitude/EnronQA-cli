"""Pinned, verified downloads and a local read-only SQLite dataset API."""

import hashlib
import json
import os
import sqlite3
import tempfile
import urllib.request
from contextlib import suppress
from pathlib import Path

REVISION = "c0b3a9190fd970e83cfbe7d399a08860e43e221e"
DATASET = "MichaelR207/enron_qa_0922"
FILES = {
    "dev-00000-of-00001.parquet": "3661cb585657061c156a408b201afbb4adf94d2e20fd41cc172c26c582800185",
    "test-00000-of-00001.parquet": "9684fe7d459195ca0873616a28956a9498c88e819c0d2cd7f5196f14513143ee",
    "train-00000-of-00002.parquet": "9b1de19cd552d19625f691e21101028965099b8e98b24b896ef3e6e078f4c447",
    "train-00001-of-00002.parquet": "873329b234e713342dee769413d4974962e8a525dc50dfea5fbd15fc25b4af0a",
}
SETS = ("train", "dev", "test", "all")


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def default_dir():
    return Path(
        os.environ.get(
            "ENRONQA_DATA_DIR",
            Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "enronqa",
        )
    )


def build_index(raw, destination):
    import pyarrow.parquet as pq

    db = sqlite3.connect(destination)
    try:
        db.executescript("""
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE documents (document_id TEXT PRIMARY KEY, email TEXT NOT NULL, user TEXT);
        CREATE TABLE questions (question_id TEXT PRIMARY KEY, split TEXT NOT NULL,
          document_id TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL, alternates TEXT NOT NULL);
        CREATE INDEX question_split ON questions(split, question_id);
        """)
        for name in FILES:
            split = name.split("-")[0]
            for batch in pq.ParquetFile(Path(raw) / name).iter_batches(batch_size=128):
                for row in batch.to_pylist():
                    path = row["path"]
                    old = db.execute(
                        "SELECT email FROM documents WHERE document_id=?", (path,)
                    ).fetchone()
                    if old is not None and old[0] != row["email"]:
                        raise ValueError(f"Conflicting email content: {path}")
                    db.execute(
                        "INSERT OR IGNORE INTO documents VALUES (?,?,?)",
                        (path, row["email"], row["user"]),
                    )
                    for i, question in enumerate(row["questions"]):
                        alternates = row["alternate_answers"][i] or []
                        if isinstance(alternates, str):
                            alternates = [alternates]
                        db.execute(
                            "INSERT INTO questions VALUES (?,?,?,?,?,?)",
                            (
                                hashlib.sha256(
                                    f"{REVISION}/{split}/{path}/{i}".encode()
                                ).hexdigest(),
                                split,
                                path,
                                question,
                                row["gold_answers"][i],
                                json.dumps(alternates),
                            ),
                        )
                db.commit()
        db.execute("INSERT INTO metadata VALUES ('revision',?)", (REVISION,))
        db.execute("INSERT INTO metadata VALUES ('schema','1')")
        db.commit()
    finally:
        db.close()


def fetch(root, progress=lambda message: None):
    root = Path(root)
    raw = root / REVISION / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        target = raw / name
        if target.is_file() and digest(target) == expected:
            progress(f"Verified {name}")
            continue
        progress(f"Downloading {name}")
        fd, temp = tempfile.mkstemp(prefix=".download-", dir=raw)
        try:
            with (
                os.fdopen(fd, "wb") as out,
                urllib.request.urlopen(
                    f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/data/{name}",
                    timeout=120,
                ) as response,
            ):
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    out.write(block)
            if digest(temp) != expected:
                raise ValueError(
                    f"Checksum verification failed for {name}; retry enronqa fetch."
                )
            os.replace(temp, target)
        finally:
            Path(temp).unlink(missing_ok=True)
    target = root / REVISION / "index.sqlite"
    if target.exists():
        try:
            with Dataset(root) as dataset:
                return dataset.counts()
        except (ValueError, sqlite3.Error):
            progress("Rebuilding invalid local index")
    progress("Building local question and email index")
    fd, temp = tempfile.mkstemp(prefix=".index-", dir=target.parent)
    os.close(fd)
    try:
        build_index(raw, temp)
        os.replace(temp, target)
    finally:
        Path(temp).unlink(missing_ok=True)
    with Dataset(root) as dataset:
        return dataset.counts()


class Dataset:
    def __init__(self, root=None):
        self.dataset_id = DATASET
        self.revision = REVISION
        directory = Path(root or default_dir())
        local_manifest = directory / "dataset.json"
        expected = {"revision": REVISION, "schema": "1"}
        if local_manifest.exists():
            manifest = json.loads(local_manifest.read_text(encoding="utf-8"))
            if manifest.get("schema") != "enronqa-local-v1" or not all(
                isinstance(manifest.get(k), str) and manifest[k].strip()
                for k in ["id", "revision", "index_sha256"]
            ):
                raise ValueError("Invalid local dataset manifest")
            path = directory / "index.sqlite"
            if not path.is_file() or digest(path) != manifest["index_sha256"]:
                raise ValueError("Local dataset index checksum mismatch")
            self.dataset_id = manifest["id"]
            self.revision = manifest["revision"]
            expected = {
                "revision": self.revision,
                "schema": "local-1",
                "dataset": self.dataset_id,
            }
        else:
            path = directory / REVISION / "index.sqlite"
        if not path.is_file():
            raise ValueError(
                f"Dataset index not found at {path}. Run: enronqa fetch --data-dir '{Path(root or default_dir())}'"
            )
        try:
            self.db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            self.db.row_factory = sqlite3.Row
            metadata = dict(self.db.execute("SELECT key,value FROM metadata"))
            if metadata != expected:
                raise ValueError("Dataset index version mismatch")
            self.db.execute(
                "SELECT question_id, split, document_id, question, answer, alternates FROM questions LIMIT 1"
            )
            self.db.execute("SELECT document_id, email, user FROM documents LIMIT 1")
        except (ValueError, sqlite3.Error) as exc:
            with suppress(Exception):
                self.db.close()
            raise ValueError(
                f"Invalid dataset index: {exc}. Run: enronqa fetch --data-dir '{Path(root or default_dir())}'"
            ) from exc

    def provenance(self):
        return {"id": self.dataset_id, "revision": self.revision}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def counts(self):
        return {
            "questions": {s: self.count(s) for s in SETS},
            "documents": self.db.execute("SELECT COUNT(*) FROM documents").fetchone()[
                0
            ],
        }

    def count(self, selection):
        if selection == "all":
            return self.db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        return self.db.execute(
            "SELECT COUNT(*) FROM questions WHERE split=?", (selection,)
        ).fetchone()[0]

    def question(self, qid):
        row = self.db.execute(
            "SELECT * FROM questions WHERE question_id=?", (qid,)
        ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["alternate_answers"] = json.loads(value.pop("alternates"))
        return value

    def document(self, did):
        row = self.db.execute(
            "SELECT * FROM documents WHERE document_id=?", (did,)
        ).fetchone()
        return dict(row) if row else None

    def questions(self, selection):
        sql, params = (
            ("SELECT question_id FROM questions ORDER BY question_id", ())
            if selection == "all"
            else (
                "SELECT question_id FROM questions WHERE split=? ORDER BY question_id",
                (selection,),
            )
        )
        for row in self.db.execute(sql, params):
            yield self.question(row[0])

    def documents(self):
        for row in self.db.execute("SELECT * FROM documents ORDER BY document_id"):
            yield dict(row)
