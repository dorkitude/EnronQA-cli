"""Shared paths and loaders for the EnronQA audit pipeline."""
from pathlib import Path
import glob
import polars as pl

REV = "c0b3a9190fd970e83cfbe7d399a08860e43e221e"
AUDIT = Path(__file__).resolve().parent.parent
RAW = AUDIT.parent / "data" / "raw" / REV / "data"
LEDGER = AUDIT / "ledger"
WORK = AUDIT / "work"
CACHE = AUDIT / "cache"
REPORT = AUDIT / "report"
SPLITS = ["train", "dev", "test"]

for d in (LEDGER, WORK, CACHE, REPORT):
    d.mkdir(parents=True, exist_ok=True)


def load_split(split: str) -> pl.DataFrame:
    files = sorted(glob.glob(str(RAW / f"{split}-*.parquet")))
    if not files:
        raise SystemExit(f"no parquet for {split} under {RAW}; run scripts/00_download.sh")
    return pl.read_parquet(files)


def questions() -> pl.DataFrame:
    return pl.read_parquet(LEDGER / "questions.parquet")


def emails() -> pl.DataFrame:
    return pl.read_parquet(LEDGER / "emails.parquet")
