"""Import explicit local QA corpora without impersonating the pinned dataset."""

import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from .data import digest


def import_local(questions_path, documents_path, destination, dataset_id):
    if not dataset_id.strip():
        raise ValueError("dataset-id must be nonblank")
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Destination already exists; choose a new dataset directory")

    def records(path):
        from .scoring import json_object, check_json_values

        with Path(path).open(encoding="utf-8") as stream:
            for line in stream:
                value = json.loads(line, object_pairs_hook=json_object)
                check_json_values(value)
                if not isinstance(value, dict):
                    raise ValueError("Expected JSON objects")
                yield value

    def text(value, key):
        result = value.get(key)
        if not isinstance(result, str) or not result.strip():
            raise ValueError("Missing/nonblank string required: " + key)
        return result

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".local-dataset-", dir=destination.parent))
    db = None
    try:
        db = sqlite3.connect(staging / "index.sqlite")
        db.executescript("""CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE documents(document_id TEXT PRIMARY KEY,email TEXT NOT NULL,user TEXT);
        CREATE TABLE questions(question_id TEXT PRIMARY KEY,split TEXT NOT NULL,document_id TEXT NOT NULL,question TEXT NOT NULL,answer TEXT NOT NULL,alternates TEXT NOT NULL);
        CREATE INDEX question_split ON questions(split,question_id);""")
        doc_ids = set()
        count = 0
        for d in records(documents_path):
            did = text(d, "document_id")
            if did in doc_ids:
                raise ValueError("Duplicate document ID: " + did)
            doc_ids.add(did)
            source = d.get("source")
            if source is not None and not isinstance(source, str):
                raise ValueError("source must be text or null")
            db.execute(
                "INSERT INTO documents VALUES (?,?,?)", (did, text(d, "text"), source)
            )
        for q in records(questions_path):
            did = text(q, "document_id")
            if did not in doc_ids:
                raise ValueError("Question references unknown document: " + did)
            split = q.get("split", "test")
            if split not in ["train", "dev", "test"]:
                raise ValueError("Invalid split")
            alternatives = q.get("alternate_answers", [])
            if not isinstance(alternatives, list) or any(
                not isinstance(a, str) or not a.strip() for a in alternatives
            ):
                raise ValueError("Invalid alternate_answers")
            db.execute(
                "INSERT INTO questions VALUES (?,?,?,?,?,?)",
                (
                    text(q, "question_id"),
                    split,
                    did,
                    text(q, "question"),
                    text(q, "answer"),
                    json.dumps(alternatives),
                ),
            )
            count += 1
        if not count:
            raise ValueError("Dataset has no questions")
        import hashlib

        revision = hashlib.sha256(
            (digest(questions_path) + digest(documents_path)).encode()
        ).hexdigest()
        db.executemany(
            "INSERT INTO metadata VALUES (?,?)",
            [("schema", "local-1"), ("revision", revision), ("dataset", dataset_id)],
        )
        db.commit()
        db.close()
        db = None
        manifest = {
            "schema": "enronqa-local-v1",
            "id": dataset_id,
            "revision": revision,
            "index_sha256": digest(staging / "index.sqlite"),
            "questions": count,
            "documents": len(doc_ids),
            "source_fields": {"text": "email", "source": "user"},
        }
        (staging / "dataset.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        os.rename(staging, destination)
        return manifest
    except sqlite3.IntegrityError as exc:
        raise ValueError("Duplicate question ID or invalid local record") from exc
    finally:
        if db is not None:
            db.close()
        if staging.exists():
            shutil.rmtree(staging)
