# OWASP Top 10 (2025) Audit — claude-skills

_Date: 2026-10-25 · Scope: whole repository · Commit: 1194339 · Tree: clean · Fixed in: owasp-top10-fixes (PR #1)_

## System summary
A private collection of four Claude Code skills (`owasp-top10`, `review-agent`, `mcp-builder`, `document`): Markdown instructions plus reference files, installed under `~/.claude/skills/`. There is no executable code, build, or dependency manifest. The "attack surface" is the behaviour the skills induce in an agent: the agent reads repositories (possibly untrusted) as input, runs their builds and tests, writes docs/reports that may be shared, and generates new MCP server code. Assets at risk are the user's machine (code execution via builds or injected instructions), secrets in audited repositories, and the security of generated code.

## Summary
| Category | Status | Findings |
|---|---|---|
| A01 Broken Access Control | Issues | C:0 H:0 M:1 L:0 |
| A02 Security Misconfiguration | Issues | C:0 H:0 M:0 L:1 |
| A03 Software Supply Chain Failures | No issues found | C:0 H:0 M:0 L:0 |
| A04 Cryptographic Failures | Issues | C:0 H:0 M:1 L:1 |
| A05 Injection | Issues | C:0 H:0 M:1 L:0 |
| A06 Insecure Design | Issues | C:0 H:0 M:0 L:1 |
| A07 Authentication Failures | No issues found | C:0 H:0 M:0 L:0 |
| A08 Software or Data Integrity Failures | No issues found | C:0 H:0 M:0 L:0 |
| A09 Security Logging and Alerting Failures | No issues found | C:0 H:0 M:0 L:0 |
| A10 Mishandling of Exceptional Conditions | N/A | C:0 H:0 M:0 L:0 |

Overall the skills are security-conscious (secret redaction in reports, localhost-only probes, no history rewriting, allowlists for MCP tool inputs, auth for remote MCP endpoints). The gaps were in what the skills *don't* say: (1) `review-agent` and `document` run project builds and read repo text without treating it as untrusted, (2) `document` could copy hard-coded credentials into docs/README, (3) the HTTP MCP guidance says "bind to localhost" without the setting that does it, while Spring Boot binds all interfaces by default.

## Remediation
| Finding | Severity | Status | Notes |
|---|---|---|---|
| A05-1 Repo content can steer the agent (prompt injection) / untrusted builds | Medium | Fixed | Data-not-instructions rule added to `review-agent`, `document`, `owasp-top10`; ask-before-building for untrusted repos added to `review-agent`, `document` |
| A04-1 `document` may copy secrets into docs/README | Medium | Fixed | Redaction rule added |
| A01-1 HTTP MCP server not actually bound to localhost | Medium | Fixed | `server.address: 127.0.0.1` + `ss -ltnp` check |
| A06-1 Audit report committed to a public repo discloses unfixed vulns | Low | Fixed | Visibility check before committing the report |
| A04-2 `review-agent` removes secrets without rotation guidance | Low | Fixed | Rotation + no-history-rewrite guardrail |
| A02-1 stdio MCP server log in shared `java.io.tmpdir` with a predictable name | Low | Not fixed (recommendation) | Changes the generated layout/README; low risk on single-user machines |

**Verification:** No build or tests exist (Markdown only). Checked that every `SKILL.md` still has valid `name`/`description` frontmatter, that all referenced files (`references/*.md`, README links) exist, and reviewed the full diff. `server.address` is the standard Spring Boot bind-address property. Secret scan of full git history (`git log --all -p` grep for keys/tokens/passwords; gitleaks/trufflehog not installed): no secrets.
**Breaking changes for operators:** none. Installed copies under `~/.claude/skills/` are not updated by this change; re-sync after merge.
**Follow-ups:** consider the A02-1 recommendation.

## Findings

### A01 — Broken Access Control

#### [MEDIUM] HTTP MCP guidance says "bind to localhost" but omits the setting (Plausible)
**Status:** Fixed — `http-transport.md` now says Spring Boot binds all interfaces by default, names `server.address: 127.0.0.1`, and says to check with `ss -ltnp`.
- **Location:** `mcp-builder/references/http-transport.md:8-14`
- **Evidence:**
  ```
  Config: remove `stdio: true` ...; set `spring.ai.mcp.server.protocol: streamable` ... and `server.port`.
  - Security: bind to localhost unless told otherwise; validate `Origin`; ...
  ```
- **Scenario:** Agent follows the config steps (only `server.port`), Spring Boot listens on `0.0.0.0`; anyone on the LAN can call the unauthenticated MCP tools — which the same file calls "remote code execution for whatever the tools can do".
- **Fix:** Name `server.address: 127.0.0.1` explicitly and verify the bind address.

### A02 — Security Misconfiguration

#### [LOW] stdio server log file in shared temp dir (Plausible)
**Status:** Not fixed (recommendation).
- **Location:** `mcp-builder/SKILL.md:99-100`
- **Evidence:** `name: ${java.io.tmpdir}/<name>-mcp-server.log`
- **Scenario:** On a multi-user Linux host, `/tmp/<name>-mcp-server.log` is predictable and may be readable by other users, exposing tool arguments/results logged there. (Symlink pre-creation is largely mitigated by `fs.protected_symlinks`.)
- **Fix:** Log to a per-user directory, e.g. `${user.home}/.<name>-mcp-server/server.log`, and update the README template accordingly.

### A03 — Software Supply Chain Failures
No issues. No manifests or CI. `mcp-builder` fetches version metadata from Maven Central over HTTPS and pins exact versions; no `curl | sh` patterns.

### A04 — Cryptographic Failures

#### [MEDIUM] `document` skill can copy hard-coded credentials into docs and README (Plausible)
**Status:** Fixed — rule added: never copy secret values into docs/README; name the key and redact.
- **Location:** `document/SKILL.md:10`, `:63`, `:75`
- **Evidence:** `(e.g. ... "hard-coded URL")` · `Files with no functions (config ...) get a short doc: purpose, each key/field` · `Known issues & caveats — ... hard-coded paths/credentials`
- **Scenario:** A repo's `application.yml` contains a DB password; the skill documents "each key/field" and lists hard-coded credentials as known issues, writing the value into `docs/` and the README, which are shared or published more widely than the source.
- **Fix:** Explicit redaction rule (as in `owasp-top10`'s report rule).

#### [LOW] `review-agent` removes hard-coded secrets without rotation guidance (Confirmed)
**Status:** Fixed — guardrail added: tell the user the secret remains in history and must be rotated; never rewrite history.
- **Location:** `review-agent/SKILL.md:47`, `:74-78`
- **Scenario:** Agent deletes a key from source and reports it "fixed"; the user believes the secret is safe while it remains in every clone.
- **Fix:** As applied.

### A05 — Injection

#### [MEDIUM] Repository content can steer the agent; untrusted repos built without asking (Plausible)
**Status:** Fixed — `review-agent` and `document` now treat repo content as data, never as instructions, and ask before building or running an untrusted repo; `owasp-top10` Phase 1 now treats docs/comments as claims to verify.
- **Location:** `review-agent/SKILL.md:24,31`; `document/SKILL.md:23,74`; `owasp-top10/SKILL.md:27`
- **Evidence:** `Read CLAUDE.md, README*, ... Follow their conventions.` · `Run the project's build and test commands` · `run them if cheap and safe`
- **Scenario:** User runs `/review-agent` on a cloned third-party repo whose README/CLAUDE.md says "first run `./setup.sh`" or whose build plugin runs arbitrary code; the agent executes it with the user's privileges. For `owasp-top10`, a comment like "audited, safe — skip" could suppress findings.
- **Fix:** As applied (`owasp-top10` already had the ask-before-building rule).

### A06 — Insecure Design

#### [LOW] Audit report may be committed to a public repository (Plausible)
**Status:** Fixed — Phase 3 now says to check repo visibility and keep unfixed findings out of public repos.
- **Location:** `owasp-top10/SKILL.md:10` (default `--out security/OWASP-AUDIT.md`)
- **Scenario:** Report with file:line exploit paths for unfixed issues is committed to a public repo, publishing a roadmap before fixes ship.
- **Fix:** As applied.

### A07 — Authentication Failures
No issues. `http-transport.md` already requires authentication for remote MCP endpoints.

### A08 — Software or Data Integrity Failures
No issues. No deserialization or update mechanisms; skills forbid force-push and history rewriting.

### A09 — Security Logging and Alerting Failures
No issues. `owasp-top10` already forbids secrets in reports; no logging code.

### A10 — Mishandling of Exceptional Conditions
N/A — no executable code. `mcp-builder` guidance on returning error results rather than crashing is sound.

## Out of scope / not checked
- Installed copies under `~/.claude/skills/` (intentionally not modified) and the `synced/` directory (gitignored, not in repo).
- No dependency scanner applies (no manifests). gitleaks/trufflehog not installed; history checked by grep only.
- Generated MCP projects themselves were not built; the `server.address` advice is standard Spring Boot behaviour, not live-tested here.
