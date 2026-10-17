#!/usr/bin/env bash
# Sign a PyInstaller one-dir bundle (dist/enronqa) with a Developer ID
# Application identity under the hardened runtime, ready for notarization.
#
#   scripts/sign-macos-bundle.sh dist/enronqa "Developer ID Application: ..." [keychain]
#
# Signs inside out: every Mach-O file under _internal/ (extension modules,
# dylibs, the Python library), then the executable with the entitlements in
# packaging/entitlements.plist. Then it verifies the signature and runs the
# signed executable, since a hardened-runtime signature that breaks loading
# only shows up at run time.
set -euo pipefail

BUNDLE="${1:?usage: $0 BUNDLE_DIR IDENTITY [KEYCHAIN]}"
IDENTITY="${2:?usage: $0 BUNDLE_DIR IDENTITY [KEYCHAIN]}"
KEYCHAIN="${3:-}"
ENTITLEMENTS="$(cd "$(dirname "$0")/.." && pwd)/packaging/entitlements.plist"
EXE="$BUNDLE/enronqa"

args=(--force --options runtime --timestamp --sign "$IDENTITY")
[ -z "$KEYCHAIN" ] || args+=(--keychain "$KEYCHAIN")

count=0
while IFS= read -r -d '' f; do
  if file -b "$f" | grep -q 'Mach-O'; then
    codesign "${args[@]}" "$f"
    count=$((count + 1))
  fi
done < <(find "$BUNDLE/_internal" -type f -print0)
echo "signed $count Mach-O files under _internal/"

codesign "${args[@]}" --entitlements "$ENTITLEMENTS" "$EXE"
codesign --verify --strict --verbose=2 "$EXE"
# Every nested Mach-O must carry a valid signature too, or notarization fails.
while IFS= read -r -d '' f; do
  if file -b "$f" | grep -q 'Mach-O'; then
    codesign --verify --strict "$f"
  fi
done < <(find "$BUNDLE/_internal" -type f -print0)

"$EXE" --version
ENRONQA_FROZEN_SELFTEST=1 "$EXE"
