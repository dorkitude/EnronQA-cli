"""Early destination checks and atomic, race-safe output publication."""

import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path


def preflight(path, force=False, directory=False):
    if path is None:
        return
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"Refusing symlink output: {path}")
    if path.exists():
        if directory:
            if not force:
                raise ValueError(
                    f"Output directory already exists: {path}. Use --force to replace it."
                )
            if not path.is_dir() or not (path / "manifest.json").is_file():
                raise ValueError(
                    "--force only replaces a sharded export directory with a manifest"
                )
            try:
                manifest = json.loads((path / "manifest.json").read_text())
                names = {s["file"] for s in manifest["shards"]} | {"manifest.json"}
                if {p.name for p in path.iterdir()} != names or any(
                    not p.is_file() or p.is_symlink() for p in path.iterdir()
                ):
                    raise ValueError(
                        "Directory contains files outside its export manifest"
                    )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Cannot safely replace export directory: {exc}"
                ) from exc
        elif path.is_dir():
            raise ValueError(f"Output is a directory: {path}")
        if not force:
            raise ValueError(
                f"Output already exists: {path}. Use --force to replace it."
            )
    if not path.parent.is_dir():
        raise ValueError(
            f"Output parent does not exist: {path.parent}. Create it first."
        )
    fd, probe = tempfile.mkstemp(prefix=".enronqa-preflight-", dir=path.parent)
    os.close(fd)
    os.unlink(probe)


@contextmanager
def output(path=None, force=False):
    if path is None:
        yield sys.stdout
        return
    path = Path(path)
    fd, temp = tempfile.mkstemp(prefix=".enronqa-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        if force:
            os.replace(temp, path)
        else:
            os.link(temp, path)  # fails atomically if another writer won
    finally:
        Path(temp).unlink(missing_ok=True)
