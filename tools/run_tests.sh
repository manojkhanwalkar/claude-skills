#!/usr/bin/env bash
# Runs every skill script's unit tests (and the validator's) under coverage, combines the results,
# and fails below the coverage gate. A Python file in a folder with no tests fails the run too, so
# a new script can't slip past the gate. Run from the repository root:
#   python3 -m pip install -r tools/requirements.txt && tools/run_tests.sh
set -euo pipefail
GATE="${COVERAGE_GATE:-95}"
ROOT="$(pwd)"
rm -f "$ROOT"/.coverage "$ROOT"/.coverage.*
# Combine whatever was measured, even when a test fails, so CI can still show the report.
trap 'python3 -m coverage combine --quiet --data-file="$ROOT/.coverage" >/dev/null 2>&1 || true' EXIT

# Every folder holding Python code (outside .git and .github) must have tests beside it.
untested=0
while IFS= read -r dir; do
  if ! compgen -G "$dir/test_*.py" >/dev/null; then
    echo "No tests for the Python code in $dir (add test_*.py next to it)" >&2
    untested=1
  fi
done < <(find . -name '*.py' ! -name 'test_*.py' -not -path './.git/*' -not -path './.github/*' \
           -not -path '*/__pycache__/*' -printf '%h\n' | sed 's#^\./##' | sort -u)
[[ $untested -eq 0 ]] || exit 1

while IFS= read -r dir; do
  echo "== $dir"
  # Each test imports its module from its own directory, so run from there.
  (cd "$dir" && python3 -m coverage run --parallel-mode --data-file="$ROOT/.coverage" \
      --source=. --omit='test_*.py' -m unittest -q)
done < <(find . -name 'test_*.py' -not -path './.git/*' -printf '%h\n' | sed 's#^\./##' | sort -u)

python3 -m coverage combine --quiet --data-file="$ROOT/.coverage"
trap - EXIT
python3 -m coverage report --data-file="$ROOT/.coverage" --fail-under="$GATE"
