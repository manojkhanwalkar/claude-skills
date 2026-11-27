# The independent review (250+ changed lines)

Read by `pr-review` Phase 2 for PRs at or over the review threshold.

**250 or more changed lines: one agent, one pass.** Start one subagent, with the strongest model, that did not write the code. It runs the checklist below and the security checks in one pass. That is both what the review threshold asks (an independent agent reviews the diff) and what the security-checks convention asks (one agent runs `security-review` and the checks that apply), and the diff is read once. Split the security checks into a second agent only when the diff is too large for one agent to read in full, and say so in the findings comment. One review agent per PR, never one agent for several PRs (its context grows with each). The agent reports and doesn't edit; Phase 3 makes the fixes. Give it:
- the PR number, the branch or worktree, the base, and the build and test commands;
- the **bug pass**: run the built-in `code-review` skill on the PR at `high` effort (`/code-review high <pr>`; from an agent, the Skill tool with skill `code-review` and args `high <pr>`). It hunts correctness bugs and CLAUDE.md violations (Claude Code v2.1.329 and later), not design, performance, resilience or compliance, so it covers the checklist's **Correctness** item only; its rows go into the table with source `code-review`, verified like any other row. If the agent can't call it (no Skill tool, or a background agent where the built-in won't run), it does **Correctness** by hand and says so in its "checked and fine" line;
- the checklist below, including its **Design** item (`design-patterns --diff origin/<base> --report-only`), its **Performance** item (`perf-review --diff origin/<base> --report-only` when it applies), and its **Concurrency** and **API** items (`concurrency-audit` and `api-audit`, each `--diff origin/<base> --report-only`, when they apply);
- the **Security checks** below;
- the review rules from Phase 1 step 4, with the **Limits** section of the `review-guidelines` skill;
- the return format: **verified findings only**, as one table with one line per finding: source (review or the skill's name), `file:line`, severity, Confirmed or Plausible, defect, scenario and fix. Below the table, the compliance and digital-regulation applicability lines and the summary rows the diff touches. Then one "checked and fine" line per check. Not an essay.

If you can't start a subagent, run the `code-review` skill on the PR, or review it yourself, rereading it as a demanding outsider would, and run the security checks in the same sitting.
