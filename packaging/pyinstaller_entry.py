"""Entry point for the standalone (PyInstaller) enronqa binary.

ENRONQA_FROZEN_SELFTEST=1 makes the binary write and read back a small
Parquet file with pyarrow, the way `enronqa fetch` indexes the dataset, then
exit. Release CI uses it to prove the native libraries were bundled, without
downloading the dataset.
"""

import os
import sys


def selftest():
    import tempfile
    from pathlib import Path

    import pyarrow as pa
    import pyarrow.parquet as pq

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "selftest.parquet"
        pq.write_table(pa.table({"path": ["a", "b"], "email": ["x", "y"]}), path)
        rows = [
            row
            for batch in pq.ParquetFile(path).iter_batches(batch_size=128)
            for row in batch.to_pylist()
        ]
    assert rows == [{"path": "a", "email": "x"}, {"path": "b", "email": "y"}], rows
    print(f"selftest ok: pyarrow {pa.__version__}, python {sys.version.split()[0]}")


if __name__ == "__main__":
    if os.environ.get("ENRONQA_FROZEN_SELFTEST") == "1":
        selftest()
        sys.exit(0)
    from enronqa.cli import app

    app(prog_name="enronqa")
