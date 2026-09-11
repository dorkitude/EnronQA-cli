# Release packaging

Run commands from the repository root with `uv` installed. Do not include the
dataset in a package. Python wheels/sdists contain code and documentation only.

```sh
uv sync --locked
uv run pytest
uv build
uv export --no-dev --no-emit-project --format requirements-txt --output-file packaging/requirements-release.txt
uv run --no-project python packaging/build_deb.py --wheel dist/enronqa_cli-0.1.0-py3-none-any.whl --version 0.1.0
```

The amd64 `.deb` includes CPython 3.12.14 and hash-pinned Python dependencies in
`/opt/enronqa-cli`. `apt install ./enronqa-cli_0.1.0_amd64.deb` installs it without
post-install Python downloads or modifying system Python. Apt may fetch OS
dependencies through the configured Ubuntu repositories.
Supported target: Ubuntu 22.04 or newer on amd64. Other systems use the wheel.
The package retains interpreter/dependency license files. Rebuild releases to
update the bundled runtime and dependencies; they are not upgraded by Ubuntu's
system-Python updates.

Homebrew packaging lives in `dorkitude/homebrew-tap`. The formula installs the
release source into an isolated environment using Homebrew Python and uv with
hash-pinned dependency requirements. The tap is separate from Homebrew core.

Before publication: test the built wheel in a fresh environment; install the
Debian package in clean Ubuntu 22.04 and 24.04 containers; run Homebrew install
and formula tests on macOS; verify checksums and ensure all CI jobs pass.
Create a GitHub release with wheel, sdist, `.deb`, pinned requirements, and
SHA256SUMS. Do not describe PyPI publication or a hosted apt repository as
available unless actually configured.
