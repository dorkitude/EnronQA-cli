#!/usr/bin/env bash
# Keep the semantic review running until every planned batch has a cached review.
# The Python runner opens a circuit after 12 consecutive transient failures (rate limit, auth);
# this wrapper waits and resumes. Safe to kill and restart at any time.
set -u
cd "$(dirname "$0")/.."
WORKERS="${1:-10}"
while true; do
  planned=$(ls work/batches | wc -l); done_n=$(ls cache/reviews 2>/dev/null | wc -l)
  if [ "$done_n" -ge "$planned" ]; then echo "$(date -u +%FT%TZ) all $planned batches done"; break; fi
  echo "$(date -u +%FT%TZ) resume: $done_n/$planned done, workers=$WORKERS"
  uv run scripts/03_semantic_review.py run --workers "$WORKERS" 2>&1 | grep --line-buffered -v DeprecationWarning
  echo "$(date -u +%FT%TZ) runner exited; sleeping 20 min before resume"
  sleep 1200
done
