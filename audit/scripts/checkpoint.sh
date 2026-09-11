#!/usr/bin/env bash
# Periodically fold cached reviews into the ledger, regenerate aggregate tables, and push them.
# Only touches audit/report aggregate files (no email text). Safe to run while the review runs.
set -u
cd "$(dirname "$0")/.."
INTERVAL="${1:-1800}"
while true; do
  uv run scripts/03_semantic_review.py collect 2>&1 | grep -v DeprecationWarning
  uv run scripts/04_aggregate.py 2>&1 | grep -v DeprecationWarning | tail -1
  uv run scripts/03_semantic_review.py status 2>&1 | grep -v DeprecationWarning > report/semantic_status.json
  ( cd .. && git add audit/report/AGGREGATES.md audit/report/aggregates.json audit/report/semantic_status.json \
      && git diff --cached --quiet || { git commit -q -m "Checkpoint semantic review aggregates ($(jq -r .questions_parsed audit/report/semantic_status.json) questions reviewed)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && (git pull -q --rebase origin main && git push -q origin main || git rebase --abort 2>/dev/null); } )
  echo "$(date -u +%FT%TZ) checkpoint: $(jq -c . report/semantic_status.json)"
  planned=$(ls work/batches | wc -l); done_n=$(ls cache/reviews | wc -l)
  [ "$done_n" -ge "$planned" ] && { echo "all done"; break; }
  sleep "$INTERVAL"
done
