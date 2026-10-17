# Claude Code skills

Personal [Claude Code](https://claude.com/claude-code) skills, installed at `~/.claude/skills/` so they're available in every project.

| Skill | What it does |
|---|---|
| [`owasp-top10`](owasp-top10/SKILL.md) | Audits a codebase against the OWASP Top 10 (2025), writes a report with file:line evidence, and optionally applies and verifies fixes (`--fix`). |
| [`review-agent`](review-agent/SKILL.md) | Reviews a whole project, then fixes bugs, refactors and removes duplication, verifying with the project's build and tests. |
| [`mcp-builder`](mcp-builder/SKILL.md) | Creates MCP servers and clients (Spring Boot + Spring AI by default, plain Java SDK, Python or TypeScript), stdio or HTTP, with an end-to-end test and a README of start/connect commands. |
| [`document`](document/SKILL.md) | Writes per-file and per-function docs plus a project summary merged into the README. |

Run one in Claude Code with `/<skill-name>`, e.g. `/owasp-top10 --fix`.
