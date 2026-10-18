#!/usr/bin/env bash
# Copy this working tree (committed, modified and untracked files that git does not ignore) and the
# ONNX models from the Mac to the Raspberry Pi over ssh, then check the models' sha256 on the Pi.
# The GitHub repo is private, so the Pi cannot `git clone` it without credentials; this also deploys
# exactly what was tested on the Mac, uncommitted changes included.
#   bash infra/rpi/sync_to_pi.sh                     # -> pi@edgeflow-pi.local:~/vedc-traffic-flow
#   bash infra/rpi/sync_to_pi.sh pi@192.168.1.101    # another host
#   REMOTE_DIR=edgeflow bash infra/rpi/sync_to_pi.sh # another directory, relative to the remote home
# Git-ignored files (.env.rpi, .venv-pi, datasets) are never sent, except models/*.onnx.
# Nothing is deleted on the Pi: a file removed on the Mac stays there until removed by hand.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET="${1:-pi@edgeflow-pi.local}"
REMOTE_DIR="${REMOTE_DIR:-vedc-traffic-flow}"
# One ssh connection for every step, so a password is asked at most once
SOCKET="${TMPDIR:-/tmp}/edgeflow-ssh-$$"
SSH=(ssh -o ConnectTimeout=10 -o ControlMaster=auto -o "ControlPath=$SOCKET" -o ControlPersist=60)
trap '"${SSH[@]}" -O exit "$TARGET" 2>/dev/null || true' EXIT
cd "$REPO_DIR"

# NUL-separated, existing files only (a tracked file deleted in the working tree is skipped)
list_files() {
  local f
  git ls-files -z --cached --others --exclude-standard | while IFS= read -r -d '' f; do
    if [[ -f "$f" ]]; then printf '%s\0' "$f"; fi
  done
  # models/ is git-ignored except .gitkeep (since e422ce7), so the models and the checksum file the Pi
  # verifies against go explicitly; only ignored ones, so a tracked file is never sent twice
  for f in models/*.onnx models/SHA256SUMS; do
    if [[ -f "$f" ]] && git check-ignore -q "$f"; then printf '%s\0' "$f"; fi
  done
}

COUNT="$(list_files | tr -cd '\0' | wc -c | tr -d ' ')"
MODELS=""
for f in models/*.onnx; do
  if [[ -f "$f" ]]; then MODELS+="${f#models/} "; fi
done
echo "== Sending $COUNT files to $TARGET:~/$REMOTE_DIR (models: ${MODELS:-none})"
"${SSH[@]}" "$TARGET" true

# bsdtar: no AppleDouble/xattr entries; GNU tar on the Pi: own mtimes, ignore libarchive pax keywords
list_files | COPYFILE_DISABLE=1 tar --null --no-xattrs --no-mac-metadata -czf - -T - |
  "${SSH[@]}" "$TARGET" "mkdir -p $(printf '%q' "$REMOTE_DIR") && tar -xzmf - --warning=no-unknown-keyword -C $(printf '%q' "$REMOTE_DIR")"

# Provenance for the report: which commit and which uncommitted files are running on the Pi
{
  echo "synced_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "commit: $(git rev-parse HEAD) ($(git log -1 --format=%s))"
  echo "uncommitted (git status --short):"
  git status --short
} | "${SSH[@]}" "$TARGET" "cat > $(printf '%q' "$REMOTE_DIR")/DEPLOYED_FROM.txt"

echo "== Model checksums on the Pi (models/SHA256SUMS)"
"${SSH[@]}" "$TARGET" "cd $(printf '%q' "$REMOTE_DIR")/models && sha256sum --ignore-missing -c SHA256SUMS"

echo "== Done. On the Pi: cd ~/$REMOTE_DIR && bash infra/rpi/setup_pi.sh (first time), then bash infra/rpi/preflight.sh"
