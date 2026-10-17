# Release packaging

Run commands from the repository root with `uv` installed. Do not include the
dataset in a package. Python wheels/sdists contain code and documentation only.

```sh
uv sync --locked
uv run pytest
uv build
uv export --no-dev --no-emit-project --format requirements-txt --output-file packaging/requirements-release.txt
uv run --no-project python packaging/build_deb.py --wheel dist/enronqa_cli-0.2.1-py3-none-any.whl --version 0.2.1
```

The amd64 `.deb` includes CPython 3.12.14 and hash-pinned Python dependencies in
`/opt/enronqa-cli`. `apt install ./enronqa-cli_0.2.1_amd64.deb` installs it without
post-install Python downloads or modifying system Python. Apt may fetch OS
dependencies through the configured Ubuntu repositories.
Supported target: Ubuntu 22.04 or newer on amd64. Other systems use the wheel.
The package retains interpreter/dependency license files. Rebuild releases to
update the bundled runtime and dependencies; they are not upgraded by Ubuntu's
system-Python updates.

## Standalone binaries and Homebrew

`enronqa.spec` builds a PyInstaller one-dir bundle (`dist/enronqa/`: the
`enronqa` executable plus `_internal/`). One-dir starts fast; one-file would
unpack about 130 MB to a temporary directory on every run. pyarrow has no
universal2 wheels, so macOS gets one bundle per architecture.

```sh
uv sync --locked --no-dev --group release --no-editable --managed-python --python cpython-3.12-macos-aarch64-none
uv run --no-sync pyinstaller --noconfirm --clean packaging/enronqa.spec
ENRONQA_FROZEN_SELFTEST=1 dist/enronqa/enronqa   # proves pyarrow's native libraries load
```

The release workflow (`.github/workflows/release.yml`) builds
`enronqa-cli_<version>_{darwin_arm64,darwin_amd64,linux_amd64,linux_arm64}.tar.gz`
on GitHub runners (Linux on Ubuntu 22.04, so glibc 2.35+). When the
`MACOS_SIGN_P12` secret is set, macOS bundles are signed with
`scripts/sign-macos-bundle.sh` (hardened runtime, `entitlements.plist`) and
notarized; the job fails unless Apple returns `Accepted`. To test signing
locally: `scripts/sign-macos-bundle.sh dist/enronqa "Developer ID Application: ..."`.

Homebrew installs these bundles through a cask, `Casks/enronqa-cli.rb` in
`dorkitude/homebrew-tap`, written by `scripts/publish-packages.sh vX.Y.Z` after
the release exists. Homebrew refuses to build formulae without the Xcode
Command Line Tools on macOS Tahoe, so the old source-building formula is
removed by the same script.

Before publication: test the built wheel in a fresh environment; install the
Debian package and the Linux bundles in clean Ubuntu 22.04 and 24.04 containers;
install the cask on macOS (CI's `homebrew` job does this from a local tap); verify checksums and ensure all CI jobs pass.
The release workflow attaches the wheel, sdist, `.deb`, pinned requirements,
the four bundles, and SHA256SUMS. Do not describe PyPI publication or a hosted apt repository as
available unless actually configured.
