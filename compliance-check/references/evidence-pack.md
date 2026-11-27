# SOX evidence pack (--evidence)

Auditors test ITGCs on a sample drawn from a population (every production change in the period, every person with access). The script builds that population and its exceptions from the GitHub API, so the evidence is machine-generated, not screenshots:

```bash
python3 -I "${CLAUDE_SKILL_DIR}/scripts/sox_evidence.py" --since <YYYY-MM-DD> [--until <YYYY-MM-DD>] \
    [--repo OWNER/NAME] [--environment production] [--emergency-label hotfix] [--incident-label incident] \
    [--bot LOGIN] --out <folder>
```

- **Where:** pass `--out` by the report rule above: `security/sox-evidence/<since>_<until>/` in a private repo, `~/.claude/security-reports/<repo>/sox-evidence/<since>_<until>/` (the script's own default) for a public or unknown one. The pack names people by GitHub login (names and ids are dropped), so never commit it to a public repo.
- **What it gathers** (one JSON file per area, `summary.md`, `exceptions.json`, `MANIFEST.sha256`):
  - *access*: admins, maintainers and writers (the list to sign off in an access review), teams, deploy keys with write access, ruleset bypass actors (`SOX-AC3`, `AC7`);
  - *change*: branch protection and rulesets, every merged PR in the period with its approvers, whether the approval covered the merged commit, emergency changes and their retrospective reviews, and commits on the default branch that came from no PR (`SOX-CM1`–`CM3`, `CM7`, `CM8`);
  - *deploy*: environments with their required reviewers, self-review and branch policy, and deployments in the period traced to a merged PR (`SOX-CM4`, `CM9`, `SOD1`);
  - *operations*: workflow runs, with scheduled jobs whose latest run failed, and incident issues closed without a linked fix (`SOX-OPS1`, `OPS3`);
  - *evidence*: Actions log retention against the period (`SOX-EVD2`), and unsigned commits (`EVD3`, Info).
- **Gaps:** a call that needs a permission the token lacks (collaborators, classic branch protection and rulesets need admin; when protection can't be read the branch controls are reported as not assessed, not as missing), backups and restore tests (in the cloud account, not GitHub), and anything over the caps are listed under "Gaps", never silently skipped. Name each gap in the report with where its evidence lives instead.
- **Approvals by bots:** gh gives a reviewer's login only, so approvals from `[bot]` logins and well-known bots don't count; name any other approving app with `--bot`.
- **Exit status:** 2, and nothing written, when gh is missing, signed out or can't read the repository.
- **Reading the exceptions:** each one is a finding with the ID from `references/sox.md`; read the code or setting before rating it. A repository with one maintainer can't have independent GitHub approvals, so every PR shows as `SOX-CM8` (and the branch as `SOX-CM1/CM2`; see `SOD5`). Report the setting once (not once per PR), and name the compensating control an auditor would test instead, such as a review by a separate agent or person recorded on each PR, then check a sample of PRs for that record.
- **Tamper evidence:** the manifest holds a SHA-256 for every file. Tell the user to keep the folder in write-once storage for the retention period (`SOX-RET1`) and to check it with `sha256sum -c MANIFEST.sha256`.
- **Report:** add an "ITGC evidence" section to the compliance report: the period, the counts of exceptions by severity, the exceptions after review, the gaps, and where the pack is.
