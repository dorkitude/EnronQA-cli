# PyInstaller spec for the standalone enronqa release binary (one-dir bundle).
#
# Build from the repository root:
#   uv sync --locked --no-dev --group release --no-editable --managed-python \
#     --python cpython-3.12-macos-aarch64-none   # or -macos-x86_64-none, -linux-x86_64-gnu, ...
#   uv run --no-sync pyinstaller --noconfirm --clean packaging/enronqa.spec
#
# Output: dist/enronqa/ (the `enronqa` executable plus `_internal/`).
# A one-dir bundle starts in well under a second; a one-file build would
# unpack ~200 MB to a temp directory on every run.
import re
from pathlib import Path

# pyarrow subpackages enronqa never imports (it only reads Parquet). Excluding
# them leaves out the native libraries only they link (Flight alone is ~20 MB);
# PyInstaller's dependency analysis still collects everything pyarrow.lib links.
EXCLUDES = [
    "pyarrow.tests",
    "pyarrow.flight",
    "pyarrow._flight",
    "pyarrow.substrait",
    "pyarrow._substrait",
    "pyarrow.cuda",
    "pyarrow._cuda",
    "pyarrow.gandiva",
    "tkinter",
]
# The pyarrow hook also collects every file in the package as data: C++
# headers, Cython sources, tests, and plain-data second copies of the shared
# libraries PyInstaller already collects as binaries.
CRUFT = re.compile(r"^pyarrow/(include|includes|src|tests)/|\.(pyx|pxd|pxi|h|hpp|cc|cpp)$")
SHARED = re.compile(r"\.(dylib|so)(\.[0-9.]+)?$")

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "packaging" / "pyinstaller_entry.py")],
    pathex=[str(root / "src")],
    excludes=EXCLUDES,
    noarchive=False,
)
# Keep SYMLINK entries: PyInstaller uses them to expose pyarrow's libraries at
# the top of _internal/, where the rewritten @rpath/$ORIGIN lookups expect them.
a.datas = [
    (dest, src, kind)
    for dest, src, kind in a.datas
    if not CRUFT.search(dest)
    and not (kind == "DATA" and SHARED.search(dest))
]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="enronqa",
    console=True,
    strip=False,
    upx=False,
    # Signing is done afterwards (see .github/workflows/release.yml), not here.
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="enronqa", strip=False, upx=False)
