# Claude Code skills

Personal [Claude Code](https://claude.com/claude-code) skills, installed at `~/.claude/skills/` so they're available in every project.

| Skill | What it does |
|---|---|
| [`owasp-top10`](owasp-top10/SKILL.md) | Audits a codebase against the OWASP Top 10 (2025), writes a report with file:line evidence, and optionally applies and verifies fixes (`--fix`). |
| [`owasp-llm-top10`](owasp-llm-top10/SKILL.md) | Audits LLM and agent code against the OWASP Top 10 for LLM Applications (2025) and for Agentic Applications (2026); `--diff` for PR reviews, `--fix` to apply and verify fixes. |
| [`compliance-check`](compliance-check/SKILL.md) | SOX (change control, segregation of duties, audit trails, money arithmetic), PII security controls (inventory, encryption, masking, logging, retention, erasure) and PCI DSS v4.0.1 (no stored CVV, PAN unreadable and masked, payment-page scripts, keys) — with a masked lead scanner for PANs and SSNs; `--diff` for PRs, `--fix` to apply and verify fixes. |
| [`digital-regulation-check`](digital-regulation-check/SKILL.md) | GDPR/UK GDPR and ePrivacy (lawful basis, consent and cookies, rights, automated decisions, transfers), DMA, DSA, AI Act, Data Act, European Accessibility Act, CRA, NIS2, DORA, plus CCPA/US state laws, COPPA, LGPD, DPDP, PIPL and others — with a tracker/cookie scanner; `--diff` for PRs, `--fix` to apply fixes. |
| [`pr-review`](pr-review/SKILL.md) | Takes a PR to merged: independent review, fixes with tests, security and compliance checks (`security-review`, `owasp-llm-top10`, `compliance-check`, `digital-regulation-check` when relevant), a findings table on the PR, green CI, squash-merge to main. |
| [`resiliency`](resiliency/SKILL.md) | Retries with exponential backoff and jitter on recoverable errors for every service-to-service call, plus token-bucket and concurrency limits (429/503 with Retry-After) and timeouts on every service; proven with failure-simulating tests and a live check. |
| [`deep-review`](deep-review/SKILL.md) | Whole-codebase review (not for PRs): performance, duplication, readability, a security recheck and resilience to failures, fixed in small verified steps. |
| [`review-agent`](review-agent/SKILL.md) | Reviews a whole project, then fixes bugs, refactors and removes duplication, verifying with the project's build and tests. |
| [`mcp-builder`](mcp-builder/SKILL.md) | Creates MCP servers and clients (Spring Boot + Spring AI by default, plain Java SDK, Python or TypeScript), stdio or HTTP, with an end-to-end test and a README of start/connect commands. |
| [`javatopython_converter`](javatopython_converter/SKILL.md) | Ports a Java project to idiomatic Python in a new IntelliJ project and a new GitHub repo, with CI (95% coverage gate), CodeQL, dependency/secret scanning, Dependabot, branch protection, golden-file parity tests, and every PR reviewed by a separate agent (`pr-review`) and security-checked. |
| [`document`](document/SKILL.md) | Writes per-file and per-function docs plus a project summary merged into the README. |

Run one in Claude Code with `/<skill-name>`, e.g. `/owasp-top10 --fix`.

`templates/` holds files the rules in `~/.claude/CLAUDE.md` tell every project to copy, such as `artifact-cleanup.yml`.

Skills with helper scripts keep their tests next to them; run them with `python3 -I -m unittest discover -s <skill>/scripts -p 'test_*.py'`.
