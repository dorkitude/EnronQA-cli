#!/usr/bin/env bash
# Publish an enronqa-cli release to the Homebrew tap (dorkitude/homebrew-tap)
# as a cask. The cask installs the release's prebuilt PyInstaller bundle for
# the machine's OS and architecture, so nothing is compiled on the user's
# machine: Homebrew needs neither Python nor the Xcode Command Line Tools
# (it refuses to build formulae without them on macOS Tahoe).
#
# Run after the GitHub release for the tag exists (the release workflow builds
# it). Needs `gh` logged in with push access to the tap. Idempotent: if the
# cask already matches the tag, nothing is committed.
#
#   scripts/publish-packages.sh v0.2.1
#   DRY_RUN=1 scripts/publish-packages.sh v0.2.1   # print, don't push
#
# For testing the cask against local builds, print it without touching any
# remote: CHECKSUMS=path/to/SHA256SUMS URL_BASE=file:///path/to/assets
# CASK_ONLY=1 scripts/publish-packages.sh v0.2.1
set -euo pipefail

TAG="${1:?usage: $0 vX.Y.Z}"
VERSION="${TAG#v}"
REPO="dorkitude/EnronQA-cli"
NAME="enronqa-cli"
DESC="EnronQA dataset access and reproducible LLM answer evaluation"
HOMEPAGE="https://github.com/${REPO}"
# Cask URLs interpolate #{version}, as `brew audit` requires.
URL_BASE="${URL_BASE:-https://github.com/${REPO}/releases/download/v#{version\}}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if [ -n "${CHECKSUMS:-}" ]; then
  cp "$CHECKSUMS" "$WORK/SHA256SUMS"
else
  echo "==> Fetching release checksums for ${TAG}" >&2
  gh release download "$TAG" -R "$REPO" -p SHA256SUMS -D "$WORK"
fi
sha_of() { awk -v f="$1" '$2 == f || $2 == "*" f {print $1}' "$WORK/SHA256SUMS"; }
asset() { echo "${NAME}_${VERSION}_$1.tar.gz"; }
url_of() { echo "${URL_BASE}/${NAME}_#{version}_$1.tar.gz"; }
for target in darwin_arm64 darwin_amd64 linux_arm64 linux_amd64; do
  [ -n "$(sha_of "$(asset "$target")")" ] || { echo "$(asset "$target") missing from SHA256SUMS" >&2; exit 1; }
done

cat > "$WORK/${NAME}.rb" <<EOF
cask "${NAME}" do
  version "${VERSION}"

  on_macos do
    on_arm do
      sha256 "$(sha_of "$(asset darwin_arm64)")"
      url "$(url_of darwin_arm64)"
    end
    on_intel do
      sha256 "$(sha_of "$(asset darwin_amd64)")"
      url "$(url_of darwin_amd64)"
    end
  end
  on_linux do
    on_arm do
      sha256 "$(sha_of "$(asset linux_arm64)")"
      url "$(url_of linux_arm64)"
    end
    on_intel do
      sha256 "$(sha_of "$(asset linux_amd64)")"
      url "$(url_of linux_amd64)"
    end
  end

  name "EnronQA-cli"
  desc "${DESC}"
  homepage "${HOMEPAGE}"

  livecheck do
    skip "Updated by scripts/publish-packages.sh on release."
  end

  # A self-contained bundle: the executable plus its _internal/ directory
  # (Python runtime and pyarrow). Homebrew links only the executable.
  binary "enronqa/enronqa"

  # Unless the release workflow signed and notarized the bundle, macOS
  # quarantines the executable and every library under _internal/ and refuses
  # to load them, so clear the attribute from the whole bundle.
  postflight_steps do
    on_macos do
      run "/usr/bin/xattr", args: ["-d", "-r", "com.apple.quarantine", "{{staged_path}}/enronqa"], must_succeed: false
    end
  end
end
EOF

if [ -n "${CASK_ONLY:-}" ]; then
  cat "$WORK/${NAME}.rb"
  exit 0
fi

publish() { # repo, path, file, message; an empty file removes path
  local repo="$1" path="$2" src="$3" msg="$4" dir
  dir="$WORK/$(basename "$1")"
  [ -d "$dir" ] || gh repo clone "$repo" "$dir" -- -q --depth 1
  if [ -z "$src" ]; then
    if ! git -C "$dir" ls-files --error-unmatch "$path" >/dev/null 2>&1; then
      echo "    $repo: $path already gone"
      return
    fi
    if [ -n "${DRY_RUN:-}" ]; then
      echo "    [dry run] would remove $path from $repo"; return
    fi
    git -C "$dir" rm -q "$path"
    git -C "$dir" commit -q -m "$msg"
    git -C "$dir" push -q origin HEAD
    echo "    $repo: removed $path"
    return
  fi
  mkdir -p "$(dirname "$dir/$path")"
  cp "$src" "$dir/$path"
  if git -C "$dir" diff --quiet -- "$path" && git -C "$dir" ls-files --error-unmatch "$path" >/dev/null 2>&1; then
    echo "    $repo: $path already up to date"
    return
  fi
  if [ -n "${DRY_RUN:-}" ]; then
    echo "    [dry run] would commit $path to $repo:"; cat "$src"; return
  fi
  git -C "$dir" add "$path"
  git -C "$dir" commit -q -m "$msg"
  git -C "$dir" push -q origin HEAD
  echo "    $repo: pushed $path"
}

echo "==> Homebrew cask"
publish dorkitude/homebrew-tap "Casks/${NAME}.rb" "$WORK/${NAME}.rb" "${NAME} ${VERSION}"
# The formula built a Python virtualenv from source, which Homebrew refuses
# without the Xcode Command Line Tools on macOS Tahoe. The cask replaces it.
publish dorkitude/homebrew-tap "Formula/${NAME}.rb" "" "${NAME}: replaced by the cask"

echo "==> Done: brew install dorkitude/tap/${NAME}"
echo "    Formula users switch once: brew uninstall ${NAME} && brew install dorkitude/tap/${NAME}"
