# Token efficiency

Sixteen rules cut the tokens spent on each change without relaxing any safety gate. They come from one long session (2026-11-21) in which full local builds, long review reports and an agent per small PR used most of the budget. They live in the owner's global rules (`~/.claude/CLAUDE.md`, rules 3, 4, 5, 7, 8, 9 and 10; [CONVENTIONS.md](CONVENTIONS.md) has the defaults the skills use for everyone else), in the skills below, and in each repo's `.github/dependabot.yml`.

## The rules

| # | Rule | Where it lives | Why it saves tokens |
|---|---|---|---|
| 1 | Locally, run only the tests for what changed: the changed modules and their dependents (`mvn -pl <module> -am`, `-Dtest=…`, `pytest <path>`). CI runs the full suite and the coverage gate; run everything locally only to reproduce what CI can't show | Rule 7; [pr-review](pr-review/SKILL.md), [fix-ci](fix-ci/SKILL.md), [test-gen](test-gen/SKILL.md) | Full builds took 3–15 minutes each, and their output came back into context |
| 2 | Reviewers return a findings table, one line per item, and a single "checked and fine" line | Rule 9; pr-review and every reviewer prompt | Review reports ran 1,500–3,000 words, each read in full |
| 3 | One security pass runs `security-review` plus whichever of `owasp-llm-top10`, `compliance-check`, `digital-regulation-check` and `ada-compatibility` apply; none of them for docs-only or CI-only diffs that can't trigger them | Rule 4; pr-review | Each separate check re-read the same diff |
| 4 | Dependabot groups minor and patch bumps per ecosystem into one weekly PR; a green group with clean release notes merges on a self-review | Rule 8; `dependabot.yml`; [pr-triage](pr-triage/SKILL.md) | Seven bumps took seven CI cycles and a review agent; grouped, two PRs |
| 5 | Only PRs that change code count toward the deep review: Dependabot, docs-only and CI-only PRs don't | Rule 5; [post-merge-sync](post-merge-sync/SKILL.md) | Fewer whole-codebase reviews, the costliest thing the skills do |
| 6 | No pr-walkthrough for small (under 250 changed lines), Dependabot or docs-only PRs | pr-review | It reads the whole diff and writes a long comment nobody needs on a version bump |
| 7 | One progress signal per background job: the agent's report or a watcher, not both; milestones only (filed, merged, failed) | Rule 9 | Duplicate notifications each cost a reply |
| 8 | Wait for CI with one background command that reports once, not repeated status checks | Rule 9; pr-review, fix-ci | Polling and logs added up across a dozen PRs |
| 9 | Mechanical agents (Dependabot reviews, CI fixes, cleanup, watchers) start with `model: sonnet` by default; only code and security reviews use the strongest | Rule 9; pr-review, pr-triage | Mechanical work doesn't need the strongest model |
| 10 | Batch small housekeeping (docs and wording fixes) into one PR per repo | Rule 9 | Every PR has a fixed cost: CI, a findings table, a merge |
| 11 | Read only what's needed: files over about 300 lines by range or after a grep; a long reference (a connector's guide such as the Docs `guide`, a skill's references) loaded once per session (see row 15); command output trimmed to its tail, docs by outline or changes since the last read | Rule 9 | Keeps large dumps out of context |
| 12 | Start a fresh session for each major task; memory, PRs and docs carry the state | Rule 9 | A long session is compacted, and every later step re-reads a bigger context |
| 13 | One background agent per PR or task, with a scoped brief; never one agent working through a batch of PRs | Rule 9; pr-review, pr-triage, fix-ci | A batch agent re-reads every earlier PR's context; the largest one used about 110M tokens |
| 14 | Run at most about 3 background agents at a time | Rule 9 | A 2026-11 session hit 15 rate-limit errors running many Opus agents at once, and agents lost work when they were cut off |
| 15 | Load a long reference once, naming the Docs connector `guide`; pass the parts an agent needs in its brief instead of having each agent reload them | Rule 9 | The same session loaded the 46k-character Docs guide 16 times, about 750k characters |
| 16 | Keep each skill description to 300 characters or less (trigger words, the main "Not for", the full Args) so Claude Code's skill listing fits its budget (about 1% of the context window, around 8,000 characters at 200k) | Rule 10 | 27 descriptions of about 1,000 characters each overflowed it, and seven skills showed with blank descriptions |

Already in place before these: PRs under 250 changed lines get a self-review instead of a separate review agent (rule 3, [#27](https://github.com/manojkhanwalkar/claude-skills/pull/27)).

## Keeping the rules current

[`token-efficiency-review`](token-efficiency-review/SKILL.md) measures token use from the local transcripts about every 10 days (a scheduled, report-only run) and proposes changes to these rules and the skills, backed by the numbers. Changes still go through a reviewed PR.

## Review history

| Date | Changes |
|---|---|
| 2026-11-21 | First `token-efficiency-review` run: about 31% of tokens went to background agents, all on the strongest model; about 97% of input was cache re-reads. Rows 9 and 11 sharpened, row 13 added |
| 2026-11-25 | Skills deep review (375M tokens in the session, 47% of them from 67 background agents): rows 14, 15 and 16 added, row 11 points to 15 |

## What stays the same

None of these rules relaxes a gate; they only change how much work is spent reaching it.

- Every change still goes through a PR, and nothing merges with failing CI or an open Critical, High or Medium finding.
- CI still runs the full test suite and the coverage gate on every PR; only local runs are narrowed.
- The security checks still run whenever the diff can trigger them, and a security-looking finding is never waived by a self-review.
- A grouped Dependabot PR with a major version, a breaking change in its notes, a failing check or a security advisory gets a full review, as before.
- Code and security reviews keep the strongest model.
