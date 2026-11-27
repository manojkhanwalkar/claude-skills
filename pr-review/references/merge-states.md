# Merge states and CI outcomes

Read by `pr-review` Phase 5 when the PR isn't simply `CLEAN` after a green run.

## Conflicts (`DIRTY`)

**`DIRTY` (conflicts):** resolve them on the branch the way the `resolve-conflicts` skill does (merge the base, keep both sides' intent, regenerate lockfiles and generated files, build and test). Ask the user if the intent is unclear. If the resolution changed reviewed code beyond taking one side, review the resolution itself (`git show --remerge-diff HEAD`, git 2.36 or later) before merging. On a PR of 250 or more lines the independent reviewer does that (the review threshold); a small PR's self-review covers it. Fix its confirmed Critical, High and Medium findings first.

## CI outcomes

- **No checks at all:** say so in the report, rely on the local build and tests, and flag the missing CI (the user's rules expect it) instead of waiting.
- **A check fails:** fix it the way the `fix-ci` skill does: read the failed job's log, find the real cause, fix it on the branch with a test, and never weaken a check. An agent started for it begins with `model: sonnet`. Then go back to Phase 3 and wait again.
- **Flaky test:** rerun once, then fix its cause as `fix-ci` describes; never add retries or flaky annotations. Commit the fix on its own, even when the test isn't the PR's, and add a findings-table row: "Flaky test `<name>`: the cause; **Fixed** in `<sha>`".
- Never merge on red, and never bypass required checks.

## Merge state after green CI

- **`BLOCKED` with every check green:** a required check is missing or renamed (see `fix-ci` Phase 1, "Blocked with nothing red"), or a required review is missing. Report a review only the user can give, and stop.
- **`UNSTABLE`:** a non-required check failed. Treat it as red.
- **`UNKNOWN`:** GitHub is still computing it. Read it again shortly.
