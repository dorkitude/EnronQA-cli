#!/usr/bin/env bash
# Download the pinned EnronQA revision into the local, git-ignored data directory.
set -euo pipefail
REV="${ENRONQA_REV:-c0b3a9190fd970e83cfbe7d399a08860e43e221e}"
DEST="${ENRONQA_RAW_DIR:-$(dirname "$0")/../../data/raw/$REV}"
BASE="https://huggingface.co/datasets/MichaelR207/enron_qa_0922/resolve/$REV"
mkdir -p "$DEST/data"
for f in README.md .gitattributes data/dev-00000-of-00001.parquet data/test-00000-of-00001.parquet data/train-00000-of-00002.parquet data/train-00001-of-00002.parquet; do
  [ -s "$DEST/$f" ] && { echo "have $f"; continue; }
  echo "fetch $f"; curl -sL --fail -o "$DEST/$f" "$BASE/$f"
done
( cd "$DEST" && sha256sum data/*.parquet > SHA256SUMS && cat SHA256SUMS )
