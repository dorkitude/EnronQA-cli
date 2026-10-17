# Changelog

## [0.2.1] - 2026-10-16

### Added

- Standalone binaries for macOS (arm64, x86_64) and Linux (amd64, arm64), built
  with PyInstaller on GitHub Actions and attached to each release as
  `enronqa-cli_<version>_<os>_<arch>.tar.gz`, with entries in `SHA256SUMS`.
  macOS bundles are signed with a Developer ID and notarized.

### Changed

- Homebrew installs the prebuilt binary as a cask instead of building a Python
  virtualenv from source, so it no longer needs Python or the Xcode Command
  Line Tools (Homebrew requires them for formulae on macOS Tahoe). Formula users
  switch once: `brew uninstall enronqa-cli && brew install dorkitude/tap/enronqa-cli`.
- Releases are built by `.github/workflows/release.yml` on tag push. The wheel,
  sdist, amd64 `.deb`, and `requirements-release.txt` assets are unchanged.

## [0.2.0] - 2026-09-11

- Configurable LLM judging and external judge inputs.

## [0.1.0] - 2026-09-11

- First release.
