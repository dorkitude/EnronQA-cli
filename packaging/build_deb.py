"""Build a self-contained amd64 Debian package. Run with uv run.

Bundles a uv-managed CPython and the wheel's dependencies; never downloads
packages during apt installation and never modifies the system Python.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--python", default="3.12.14")
    args = parser.parse_args()
    if not args.wheel.is_file():
        parser.error("wheel does not exist")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="enronqa-deb-") as tmp:
        work = Path(tmp)
        managed = work / "managed"
        run("uv", "python", "install", args.python, "--install-dir", str(managed), "--no-bin")
        interpreters = [p for p in managed.glob("cpython-*-linux-x86_64-gnu") if not p.is_symlink()]
        if len(interpreters) != 1:
            raise RuntimeError("Expected one Linux amd64 standalone interpreter")
        root = work / "root"
        home = root / "opt/enronqa-cli"
        shutil.copytree(interpreters[0], home, symlinks=True)
        python = home / "bin/python3"
        # This is our private staging copy, never the host or uv's cached runtime.
        run("uv", "pip", "install", "--python", str(python), "--break-system-packages", "--require-hashes",
            "-r", "packaging/requirements-release.txt")
        run("uv", "pip", "install", "--python", str(python), "--break-system-packages", "--no-deps", str(args.wheel.resolve()))
        # Entry-point shebangs contain staging paths; wrapper uses python -m.
        bindir = root / "usr/bin"
        bindir.mkdir(parents=True)
        wrapper = bindir / "enronqa"
        wrapper.write_text('#!/bin/sh\nexec /opt/enronqa-cli/bin/python3 -I -m enronqa "$@"\n')
        wrapper.chmod(0o755)
        for cache in home.rglob("__pycache__"):
            shutil.rmtree(cache)
        for file in (home / "bin").iterdir():
            if file.is_file() and not file.is_symlink():
                with file.open("rb") as stream:
                    prefix = stream.read(2)
                if prefix == b"#!":
                    text = file.read_text()
                    file.write_text(text.replace(str(home), "/opt/enronqa-cli"))
        control = root / "DEBIAN"
        control.mkdir()
        size = sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) // 1024
        (control / "control").write_text(
            f"Package: enronqa-cli\nVersion: {args.version}\nArchitecture: amd64\n"
            "Maintainer: Kyle Wild <kyle@kylewild.com>\nSection: science\nPriority: optional\n"
            "Depends: libc6 (>= 2.35), libgcc-s1, libstdc++6, zlib1g, ca-certificates\n"
            f"Installed-Size: {size}\nHomepage: https://github.com/dorkitude/EnronQA-cli\n"
            "Description: Reproducible EnronQA dataset and LLM evaluation CLI\n"
            " Bundles an isolated Python runtime and dependencies. Dataset fetched separately.\n"
        )
        docs = root / "usr/share/doc/enronqa-cli"
        docs.mkdir(parents=True)
        shutil.copyfile("LICENSE", docs / "copyright")
        # Dependency and interpreter license files are retained in /opt.
        run("dpkg-deb", "--root-owner-group", "--build", str(root),
            str(args.output_dir / f"enronqa-cli_{args.version}_amd64.deb"))

if __name__ == "__main__":
    main()
