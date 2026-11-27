# Agent-written and Dependabot PRs

**PRs written by agents.** A PR that an implementer agent opened, in this session or earlier, gets the same review as any other:
- Its author never reviews it. On a PR of 250 or more lines, the reviewer is a new subagent; never send the review to the implementer. On a small PR, your self-review counts because you didn't write the code. Read the diff itself, not the implementer's summary.
- The implementer's claims are checked like any PR body's: tests pass, coverage, "walkthrough done", "security clean". This skill's own steps run here: the walkthrough, the security pass, `documenter` and the findings table. Reuse only what is on the PR, such as a walkthrough comment for the current head or a `Docs:` commit.

**Dependabot.** A grouped Dependabot PR of minor and patch bumps that is green, and whose release notes show nothing breaking, takes the self-review path at any size; lockfiles inflate the count. A major version, a breaking change, a failing check or a security advisory gets the full review. Any agent it needs starts with `model: sonnet`.
