---
name: token-efficiency-review
description: Measure how Claude Code spent tokens since the last review (agents, tools, re-reads, polling, rate limits, the skill-listing budget) from local transcripts with a numbers-only script, and propose rule and skill changes through a reviewed PR. Use about every 10 days, on the scheduled run, or to cut token use. Not for code performance (perf-review). Args - [--since TIME] [--report-only].
---

# Token Efficiency Review

The rules in `efficiency.md` (in this repo) and rule 9 of `~/.claude/CLAUDE.md` came from one session's experience. Usage changes as projects and habits change, so this skill measures it again about every 10 days, checks whether the rules are followed and still aimed at the biggest costs, and proposes changes backed by the numbers.

## Arguments

- **`--since TIME`**: the start of the period, an ISO date or time. Default: the timestamp in `~/.claude/token-efficiency/last-run`, or 10 days ago when there is none.
- **`--report-only`**: Phases 1–3 only: write the report and the proposals, change nothing. The scheduled run uses this.

## Rules that always apply

- **Transcripts are private.** They hold prompts, code, keys and personal data. Read them only through `scripts/usage_report.py`, which prints numbers, tool, skill and model names, a command's program name (plus a short subcommand for a few known programs), and agent descriptions (written by the model when it started each agent). Never open, quote or summarise a transcript's content, and never put it in a report, PR, issue or doc.
- **The report stays local.** It goes to `~/.claude/token-efficiency/reports/<date>.md`. It names agents by their model-written descriptions, so it is never committed or published. What reaches the public repo is only the resulting rule text, with rounded numbers ("about 30% of tokens went to background agents"), never project names.
- **Never relax a gate.** A proposal may cut the work spent reaching a gate, never the gate: no fewer PRs, no skipped security checks where they apply, no merging on red CI, no lower coverage gate. Proposals that would are dropped.
- **Changes go through a PR.** Skill and `efficiency.md` changes go to the claude-skills repo through `pr-review`. Edits to `~/.claude/CLAUDE.md` need the user's yes in this session; the scheduled run never edits it.

## Phase 1 – Measure

1. Work out the period (Arguments). Then run the script once (add `--json` only if you need the raw numbers; `--context 1000000` when the sessions ran with a 1M-token context window):
   ```bash
   python3 -I ~/.claude/skills/token-efficiency-review/scripts/usage_report.py --since <time> --top 10
   ```
2. Note the headline numbers: total tokens, the share spent by background agents, cache reads (re-reading a long conversation) and writes, output tokens, compactions, API errors (rate limits), polling commands (sleeps and checks calls that don't wait by themselves; one background `--watch` is the recommended pattern and isn't counted), the tools whose results took the most characters, results repeated with the same size (the **Times** column: usually the same guide or file loaded again), the skills and slash commands used, and the **Skill listing** section: how many characters the installed skills' descriptions take against Claude Code's listing budget (1% of the context window at about 4 characters per token, shared with built-in and plugin skills; over it, some skills are listed without a description and trigger worse).
3. Read the previous report, `~/.claude/token-efficiency/reports/latest.md`, if it exists, before Phase 3 overwrites it, to see the trend.

## Phase 2 – Compare with the rules

Read `efficiency.md`, rule 9 and the efficiency lines in rules 3–8 of `~/.claude/CLAUDE.md`, and check what the numbers show against each rule. Below, **E***n* is row *n* of `efficiency.md`'s table and **C***n* is rule *n* of `CLAUDE.md`:

| Signal in the report | Points at |
|---|---|
| Cache reads are most of the tokens; compactions above 0 | Long sessions: E12 (fresh sessions), and reading less per turn (E11) |
| Background agents take a large share; the top agents are reviews of small or version-only PRs | C3's small-PR self-review and E4 / C8's Dependabot path not being used; E9's smaller model for mechanical agents |
| A top agent ran on the strongest model for mechanical work | E9 (smaller models) |
| Many polling commands | E8 (one background wait) |
| Bash results dominate; the largest results are builds or test runs | E1 (targeted tests), and trimming output (E11) |
| Read, docs or web results dominate | E11 (read by range, outline or delta) |
| A large result repeated many times (Times column) | E11 (load a long reference once per session) |
| Many rate-limit errors | Too many background agents at once: E13's one agent per task still holds, but start fewer at a time |
| A skill appears often and its runs are costly | That skill's own steps: where does it read or run more than it needs? |
| Skill listing over its budget, or descriptions over the target | Shorter descriptions: what the skill does, when to use it, when not, and its args, with detail moved to the body. For what each skill costs in context, the user can run the built-in `/skill-doctor` in an interactive session |

For each finding, say whether an existing rule covers it (and is being ignored, or needs sharper wording) or whether a new rule is needed. Look up the skill text before proposing a change to it.

## Phase 3 – Report

Write `~/.claude/token-efficiency/reports/<YYYY-MM-DD>.md`, and write the same text to `~/.claude/token-efficiency/reports/latest.md` (Write creates the folder):
- the period and the headline numbers, with the change since the previous report;
- the top findings, each with its evidence (numbers only);
- the proposals, as a table: rule or skill, the change in one line, the evidence, the expected saving (rough), and whether it relaxes any gate (it must not).

With `--report-only`, stop here and tell the user where the report is, in one line. A scheduled run also sends a desktop notification when `notify-send` exists.

## Phase 4 – Apply (not with --report-only)

1. Show the user the proposals and ask which to apply.
2. **Skills and `efficiency.md`:** one branch in the claude-skills repo, the accepted changes, a row per change in `efficiency.md`'s table, and the README's change log; open the PR and take it through `pr-review`. Under 250 changed lines it is a self-review.
3. **`~/.claude/CLAUDE.md`:** apply only the rule edits the user accepted, after their yes.
4. **Docs:** update the "Token Efficiency" Claude Doc and the "Claude Skills" catalogue doc if the project memory names them.

## Phase 5 – Record

Write the report's **Generated** timestamp (the script's clock, with its zone, for example `2026-12-01T10:00:00-05:00`) to `~/.claude/token-efficiency/last-run`, also after `--report-only`, so the next run starts exactly where this one's data ended. Never invent a time.

## Scheduling

The review is meant to run about every 10 days. It reads local files, so it runs on the user's machine, not as a cloud routine: a systemd user timer (Linux) or launchd agent (macOS) runs it headless in report-only mode, for example on the 1st, 11th and 21st of each month:

```bash
claude -p "/token-efficiency-review --report-only" --allowedTools \
  "Skill" "Read(~/.claude/skills/**)" "Read(~/.claude/token-efficiency/**)" "Read(~/.claude/CLAUDE.md)" \
  "Bash(python3 -I ~/.claude/skills/token-efficiency-review/scripts/usage_report.py *)" \
  "Edit(~/.claude/token-efficiency/**)" "Bash(notify-send *)"
```

`Edit(...)` rules also cover Write. These permissions let it run only the report script (typed with the `~` path exactly as in Phase 1), read the skills and its own reports, and write inside `~/.claude/token-efficiency/`; it cannot read transcripts directly, run other code or touch the user's rules. The user then reads `latest.md` and runs `/token-efficiency-review` in a normal session to apply what they accept.
