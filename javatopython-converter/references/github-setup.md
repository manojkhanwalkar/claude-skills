# GitHub setup for the Python project

All of this lands in **PR 1 (Scaffold)**, except the repository settings, which are API calls.
Modelled on the user's other projects.

## Pin actions to commit SHAs

Every `uses:` is pinned to a full commit SHA with the tag in a trailing comment; Dependabot
keeps them current. The SHAs below were current in Nov 2026. **Re-resolve them when you
create the project** and use the newer one if the tag moved:

```bash
for r in actions/checkout actions/setup-python astral-sh/setup-uv actions/upload-artifact \
         actions/download-artifact aquasecurity/trivy-action \
         gitleaks/gitleaks-action actions/dependency-review-action; do
  t=$(gh api repos/$r/releases/latest --jq .tag_name); echo "$r $t $(gh api repos/$r/commits/$t --jq .sha)"
done
# codeql-action's "latest release" is a codeql-bundle tag, not an action version: pin the major tag
echo "github/codeql-action v4 $(gh api repos/github/codeql-action/commits/v4 --jq .sha)"
```

| Action | Tag | SHA |
|---|---|---|
| actions/checkout | v7 | 3d3c42e5aac5ba805825da76410c181273ba90b1 |
| astral-sh/setup-uv | v10.3.3 | 68559e99cc807c1eb7e9238fd43a15bba460eec2 |
| actions/setup-python | v7.1.0 | 6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 |
| actions/upload-artifact | v7 | cf430e030ddbb5b0abf93d22962f4752f3646cd9 |
| actions/download-artifact | v8 | 9000827ccba6bdab643e8b6fd33ac0654aef8333 |
| github/codeql-action/* | v4 | 33d7b85da1a04171e211befe2c739303b9a4c066 |
| aquasecurity/trivy-action | v0.36.0 | ed142fd0673e97e23eac54620cfb913e5ce36c25 |
| gitleaks/gitleaks-action | v3.0.0 | e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e |
| actions/dependency-review-action | v5.0.0 | a1d282b36b6f3519aa1f3fc636f609c47dddb294 |

Every workflow: top-level `permissions: contents: read`, widen per job only where needed,
`persist-credentials: false` on checkout, a `timeout-minutes` on every job.

## `.github/workflows/ci.yml`

```yaml
# Lint, type-check, test and enforce 95% coverage on every PR and on main.
name: CI

on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}

jobs:
  test:
    name: Lint, type-check, test
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3
        with:
          enable-cache: true
      - name: Install
        run: uv sync --locked --all-groups
      - name: Lint
        run: |
          uv run ruff check --output-format=github .
          uv run ruff format --check .
      - name: Type-check
        run: uv run mypy
      # fail_under = 95 in pyproject.toml is the coverage gate
      - name: Test with coverage (gate 95%)
        run: uv run pytest
      - name: Coverage summary
        if: always()
        run: uv run coverage report --format=markdown >> "$GITHUB_STEP_SUMMARY" || true
      - name: Upload coverage report
        if: always()
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7
        with:
          name: coverage
          path: coverage.xml
          retention-days: 7
          if-no-files-found: ignore
      - name: Build distribution
        run: uv build
```

If the Java project needs to run for golden-test capture in CI (normally it doesn't — golden
files are committed), add a separate job; don't make the Python CI depend on a JDK otherwise.

## `.github/workflows/codeql.yml`

```yaml
# Private repos without GitHub Code Security can't upload to code scanning: CodeQL still runs
# security-extended and fails the job on any finding; the SARIF is kept as an artifact.
name: CodeQL

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: "23 4 * * 1"

permissions:
  contents: read

jobs:
  analyze:
    name: Analyze (${{ matrix.language }})
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
      actions: read
      # security-events: write   # only when uploading (public repo or Code Security enabled)
    strategy:
      fail-fast: false
      matrix:
        language: [python, actions]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - uses: github/codeql-action/init@33d7b85da1a04171e211befe2c739303b9a4c066 # v4
        with:
          languages: ${{ matrix.language }}
          build-mode: none
          queries: security-extended
      - uses: github/codeql-action/analyze@33d7b85da1a04171e211befe2c739303b9a4c066 # v4
        with:
          category: /language:${{ matrix.language }}
          upload: never        # "always" + security-events: write on a public repo
          output: sarif-results
      - name: Keep the results
        if: always()
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7
        with:
          name: codeql-${{ matrix.language }}
          path: sarif-results
          retention-days: 14
      - name: Fail on any finding
        run: |
          count=$(jq '[.runs[].results[]?] | length' sarif-results/*.sarif | awk '{s+=$1} END {print s+0}')
          jq -r '.runs[].results[]? | "\(.ruleId): \(.locations[0].physicalLocation.artifactLocation.uri):\(.locations[0].physicalLocation.region.startLine) \(.message.text | split("\n")[0])"' sarif-results/*.sarif
          echo "CodeQL findings: $count"
          test "$count" -eq 0
```

On a **public** repo, set `upload: always`, grant `security-events: write`, and drop the
"Fail on any finding" step (code scanning alerts + the required check do the job).

## `.github/workflows/security.yml`

```yaml
# Dependency and secret checks on every PR.
name: Security

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  # Public repo: use dependency-review (below). Private repo without Code Security: Trivy scans
  # uv.lock; a fixable HIGH/CRITICAL advisory fails the PR.
  dependency-scan:
    name: Dependency scan
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - uses: aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25 # v0.36.0
        with:
          scan-type: fs
          scan-ref: .
          scanners: vuln
          severity: CRITICAL,HIGH
          ignore-unfixed: true
          exit-code: "1"

  # Uncomment for a public repo (or a private one with Code Security):
  # dependency-review:
  #   name: Dependency review
  #   if: github.event_name == 'pull_request'
  #   runs-on: ubuntu-latest
  #   timeout-minutes: 10
  #   steps:
  #     - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
  #       with:
  #         persist-credentials: false
  #     - uses: actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0
  #       with:
  #         fail-on-severity: high

  secrets:
    name: Secret scan
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
      pull-requests: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: gitleaks/gitleaks-action@e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e # v3.0.0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}   # only needed for org-owned repos
```

## `.github/workflows/release.yml` (CD)

```yaml
# Push a tag like v0.2.0 to build the wheel and sdist and attach them to a GitHub release.
name: Release

on:
  push:
    tags: ["v*.*.*"]

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3
      - name: Set version from tag
        run: uv version "${GITHUB_REF_NAME#v}"
      - run: uv sync --locked --all-groups
      - run: uv run pytest
      - run: uv build
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7
        with:
          name: dist
          path: dist/

  github-release:
    needs: build
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8
        with:
          name: dist
          path: dist
      - name: Create release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: gh release create "$GITHUB_REF_NAME" --repo "$GITHUB_REPOSITORY" --generate-notes dist/*
```

If the Java project shipped a container image, add a Dockerfile (slim Python base, non-root
user, `uv sync --locked --no-dev`) and an `images` job
(`docker/setup-buildx-action`, `login-action`, `metadata-action`, `build-push-action` with
provenance + SBOM, then a Trivy image scan) — resolve those actions' SHAs the same way, and add
the `docker` ecosystem to Dependabot. Publishing to PyPI needs the user's decision (trusted
publishing setup on pypi.org); don't add it unasked.

## `.github/workflows/artifact-cleanup.yml`

Copy `~/.claude/skills/templates/artifact-cleanup.yml` and replace `__WORKFLOWS__` with the exact
names of this repo's workflows that upload artifacts (here: `CI, CodeQL, Release, Security`).
Whenever one of them finishes a run, it deletes older runs' artifacts and keeps only the newest
completed run's, per artifact kind, branch and source repository (rule 8). Keep the list in sync
when a workflow is added or renamed.

## `.github/dependabot.yml`

```yaml
version: 2
updates:
  - package-ecosystem: uv
    directory: /
    schedule:
      interval: weekly
    groups:
      uv-minor-and-patch:
        update-types: [minor, patch]
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    groups:
      actions-minor-and-patch:
        update-types: [minor, patch]
  # - package-ecosystem: docker      # if there is a Dockerfile
  #   directory: /
  #   schedule:
  #     interval: weekly
  #   groups:
  #     docker-minor-and-patch:
  #       update-types: [minor, patch]
```

Minor and patch bumps arrive as one weekly PR per ecosystem (rule 8); majors stay separate.
`pr-triage` takes them through `pr-review`.

## `.github/pull_request_template.md`

```markdown
## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## Java parity

<!-- Which Java classes/tests this ports (paths + the Java commit). List any Java test not ported and why, and any intentional behaviour difference. -->

## Checklist

- [ ] `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` pass
- [ ] Tests added or ported; every behaviour change has a test that fails without it
- [ ] Coverage ≥ 95% (`uv run pytest`); if not, what is uncovered and why: …
- [ ] Golden/parity tests pass for every external contract touched
- [ ] Timeouts on outbound calls; retries only on recoverable, idempotent calls; limits on services
- [ ] No secrets or PII in code, logs, errors or fixtures
- [ ] Design doc / system diagram updated if behaviour, APIs, data or architecture changed
```

## `.github/CODEOWNERS`

```
* @<owner>
/.github/ @<owner>
```

Use the repo owner's GitHub login (from `gh api user --jq .login`) — it's the user's own
account, so it's fine to write. Don't invent team handles.

## `SECURITY.md`

```markdown
# Security policy

## Reporting a vulnerability

Please do **not** open a public issue. Use GitHub's private vulnerability reporting instead
(*Security → Report a vulnerability* on this repository).
<!-- Private repo: private vulnerability reporting isn't available; replace the line above with
     "Contact the maintainer (<owner>) directly" — never write a personal email address unasked. -->

## Handling data

<!-- Carry over any data-handling rules from the Java project (PII, secrets, logging). -->

Never commit secrets or `.env` files. Test data must be synthetic.
```

## Settings (API calls after the repo exists)

```bash
R=<owner>/<name>
gh api -X PATCH repos/$R -F delete_branch_on_merge=true -F allow_squash_merge=true \
  -F allow_merge_commit=false -F allow_rebase_merge=false
gh api -X PUT repos/$R/vulnerability-alerts            # Dependabot alerts
gh api -X PUT repos/$R/automated-security-fixes        # Dependabot security updates
gh api -X PUT repos/$R/private-vulnerability-reporting   # public repos only
# Secret scanning + push protection (free on public repos; private needs Secret Protection):
gh api -X PATCH repos/$R --input - <<'EOF'
{"security_and_analysis":{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}}
EOF
```

A call that fails with 403/422 because the plan doesn't include the feature (common on private
repos): don't retry, note it in the final report and the design doc. Gitleaks and Trivy in
`security.yml` cover secret and dependency scanning in that case.

## Branch protection (after PR 1's CI has run)

Use the exact check names from the PR 1 run (`gh pr checks <n>`):

```bash
gh api -X PUT repos/$R/branches/main/protection --input - <<'EOF'
{
  "required_status_checks": {"strict": true, "contexts": [
    "Lint, type-check, test", "Analyze (python)", "Analyze (actions)",
    "Dependency scan", "Secret scan"]},
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
```

`required_pull_request_reviews` stays `null` for a single-maintainer repo (GitHub won't let
the author approve their own PR, so requiring a review would block every merge); the
separate-agent review via `pr-review` is the review gate. If the repo has other
collaborators, set `{"required_approving_review_count": 1, "require_code_owner_reviews": true}`.
Branch protection on a private repo needs GitHub Pro or higher; if it returns 403, say so.
