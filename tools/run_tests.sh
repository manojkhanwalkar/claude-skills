#!/usr/bin/env bash
# Runs every skill script's unit tests (and the validator's) under coverage, combines the results,
# and fails below the coverage gate. Run from the repository root:
#   python3 -m pip install -r tools/requirements.txt && tools/run_tests.sh
set -euo pipefail
GATE="${COVERAGE_GATE:-95}"
ROOT="$(pwd)"
rm -f "$ROOT"/.coverage "$ROOT"/.coverage.*
for dir in */scripts tools; do
  [[ -d "$dir" ]] || continue
  compgen -G "$dir/test_*.py" >/dev/null || continue
  echo "== $dir"
  # Each test imports its module from its own directory, so run from there.
  (cd "$dir" && python3 -m coverage run --parallel-mode --data-file="$ROOT/.coverage" \
      --source=. --omit='test_*.py' -m unittest -q)
done
python3 -m coverage combine --quiet --data-file="$ROOT/.coverage"
python3 -m coverage report --data-file="$ROOT/.coverage" --fail-under="$GATE"
