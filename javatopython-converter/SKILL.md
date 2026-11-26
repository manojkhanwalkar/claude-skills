---
name: javatopython-converter
description: Convert a Java project (Spring Boot, MCP, CLI or library) into a behaviour-equivalent Python project in a new repo, with golden-file parity tests, a 95% coverage gate and every PR through pr-review. Use to port, convert or migrate Java to Python. Not for a chat snippet or keeping a port in step (port-parity). Args - [JAVA_PATH] [--name NAME] [--dir DIR] [--public] [--module PATH] [--no-merge].
license: Apache-2.0
---

# Java → Python converter

Turn a Java project into a new, standalone Python project that does the same thing, is
idiomatic Python, and arrives with the same engineering process as every other project:

1. A **new IntelliJ project** in its own directory.
2. A **new GitHub repository**, set up like the others (CI, security, Dependabot, branch protection).
3. The code arrives through **PRs**, each taken through `pr-review` (an independent reviewer on PRs of 250 or more changed lines, a self-review below that), security-checked, and merged only on green CI.
4. **Behaviour parity** with the Java original is proven by tests, not assumed.

The Java project is the source of truth and is **never modified**.

## Arguments and defaults

| Arg | Default |
|---|---|
| Java project path | current directory |
| `--name` | `<JavaProjectName>Py` (e.g. `OrderService` → `OrderServicePy`) |
| `--dir` | `~/IdeaProjects` → project at `~/IdeaProjects/<name>` |
| Visibility | **private**; `--public` for public |
| `--module` | whole project |
| `--no-merge` | merge each PR after review and green CI |

Stop and ask before starting if the target directory already exists and isn't empty, or a GitHub repo with that name already exists (`gh repo view <owner>/<name>`). Never overwrite either.

## Phase 0 – Check the tools

Run these once; stop and say what's missing:

```bash
gh auth status                 # needs repo + workflow scopes
uv --version                   # project and venv manager
python3 --version              # pick the newest stable CPython uv can install (uv python list)
git -C <java-path> status      # source must be a clean git checkout
```

Record the **source SHA** (`git -C <java-path> rev-parse HEAD`). It becomes the parity baseline
that `port-parity` later diffs from, so it must be on the remote default branch
(`git -C <java-path> fetch && git -C <java-path> merge-base --is-ancestor HEAD origin/<default>`);
if it isn't, ask the user whether to push it or convert from `origin/<default>` instead.

Note the Java build tool (`mvnw`/`mvn`/`gradlew`) and run the Java build **and tests** once as
the baseline. Record pass/fail counts. If Java tests already fail, record which ones and tell
the user; those behaviours are not a parity target until they decide.

## Phase 1 – Understand the Java project

Read, don't skim. Build an inventory (keep it; it goes into the design doc):

- **Modules** and their dependency order (bottom-up: libraries → services → clients → apps).
- **Entry points:** `main` classes, Spring Boot apps, CLIs, MCP servers/clients, scheduled jobs.
- **Public surface** — the contract the Python version must keep:
  - HTTP endpoints (method, path, request/response JSON, status codes, headers);
  - MCP tools (name, description, input schema, output) and transport (stdio / Streamable HTTP);
  - CLI arguments, exit codes, stdout/stderr formats;
  - config properties and environment variables;
  - files, databases or queues it reads or writes, with formats.
- **Dependencies:** each one, what it is used for, and its Python counterpart (see `references/idioms.md`).
- **Tests:** what they cover. These are the first source of parity cases.
- **Cross-cutting:** logging, error handling, security controls (auth, validation, size limits), resilience (timeouts, retries, rate limits), concurrency.
- **LLM/agent code:** prompts, model calls, MCP/A2A, tools, RAG, memory → decides whether `owasp-llm-top10` applies (the security-checks convention).

Then write the **conversion plan**:
- Java module → Python package mapping and the target layout.
- Library mapping, one line per Java dependency.
- Decisions that change shape (e.g. Spring Boot → FastAPI; Spring AI MCP → official `mcp` SDK; threads → asyncio). Apply the defaults in `references/idioms.md`; **ask the user only when a choice changes the external contract or there is no sensible default.**
- The PR sequence (Phase 4).

## Phase 2 – Design doc and system diagram

The design-doc convention (`${CLAUDE_SKILL_DIR}/../CONVENTIONS.md`; the user's `CLAUDE.md` overrides every convention named here) makes these optional: create them when the user's rules ask for them, otherwise ask once. Look for existing ones first: `Artifact` list and the new project's memory. Then:
- **Design doc** — a Claude Doc named exactly `<name>`. Sections: Purpose, Origin (link the Java repo and commit SHA converted), Architecture, Module mapping, Library mapping, Public contract, Parity strategy, Performance/resilience/scale trade-offs (the resilience convention), Security, Testing and coverage, Open questions.
- **System diagram** — a Design canvas named `<name> System Diagram`: a system page plus one page per major flow.

After each merge, `post-merge-sync` updates both when the PR changed behaviour, APIs, data or architecture.

## Phase 3 – Create the IntelliJ project and the GitHub repository

**Confirm with the user before creating the GitHub repo** (it's outward-facing): show the repo name, owner and visibility in one line and wait for a yes, unless they already said to go ahead.

1. **Local project** at `<dir>/<name>`:
   ```bash
   mkdir -p <dir>/<name> && cd <dir>/<name>
   git init -b main
   uv init --lib --name <dist_name> --python <version>   # <dist_name> = snake_case of <name>
   ```
   Then write `pyproject.toml`, `.gitignore`, `README.md` and `LICENSE` (copy the Java project's license if it has one) per `references/project-layout.md`.
2. **IntelliJ project:** create `.idea/` and `<name>.iml` per `references/intellij.md` so that opening the folder in IntelliJ gives a Python module with `src/` and `tests/` marked and the uv `.venv` as the SDK. Run `uv sync` so `.venv` exists. If the IntelliJ Python plugin isn't installed (no `python` / `PythonCore` under `~/.local/share/JetBrains/<IDE>/` and not bundled), tell the user to install it from *Settings → Plugins*; the project files still work once it is.
3. **Bootstrap commit on `main`** — the one commit that can't go through a PR because there is no repo yet. Keep it minimal: `README.md` (one paragraph: what this is and that it's a port of `<java repo>`), `LICENSE`, `.gitignore`. Nothing else.
4. **GitHub repo:**
   ```bash
   gh repo create <owner>/<name> --private --source . --remote origin --push \
     --description "Python port of <JavaName>"
   ```
   Use `--public` instead of `--private` when the user passed `--public` or chose a public repo.
5. **Repository settings** — see `references/github-setup.md` §Settings: secret scanning + push protection, Dependabot alerts and security updates, private vulnerability reporting (public repos), auto-delete head branches, squash-merge only. Branch protection on `main` is set **after PR 1's CI has run once**, so the required check names exist.
6. **Project memory** for the new project (`~/.claude/projects/<encoded path of the new dir>/memory/`, the absolute path with every character other than `A–Z`, `a–z` and `0–9` replaced by `-`):
   - the Java origin (repo + source SHA), and the design doc and diagram links;
   - the counters `post-merge-sync` keeps (total merged PRs, merged since the last deep review, last deep review, last sync), at 0 with no last deep review or sync yet; that skill maintains them from here on;
   - the **link `port-parity` reads**, in its exact `## Parity link` format (port-parity §Parity memory): Role target, the Java repo as source and this one as target (repo, local path, default branch), and the full source SHA as the parity baseline.

   Write the same block with Role source into the **Java project's memory** too (memory only; the Java repo is never touched). The parity backlog lives there: `post-merge-sync` adds a line to it whenever a Java PR changes the contract. Update existing memory files rather than adding duplicates, and add one-line pointers to each `MEMORY.md`.

## Phase 4 – Convert through PRs

Every change from here on goes through a PR (the PR policy): branch from up-to-date `main`, commit, push, `gh pr create`. Recommended sequence — merge each before starting the next, so later PRs build on reviewed code:

| PR | Contents |
|---|---|
| 1 – Scaffold | `pyproject.toml` with tooling (ruff, mypy strict, pytest, pytest-cov `fail_under = 95`), `uv.lock`, `.python-version`, `src/<pkg>/__init__.py`, one smoke test, all of `.github/` (CI, CodeQL, security scan, release, artifact cleanup, Dependabot, PR template, CODEOWNERS), `SECURITY.md`, the IntelliJ files. From `references/github-setup.md`. |
| 2…n – One module each | Bottom-up dependency order. For each: port the Java tests first as Python tests (they should fail), then the code until they pass, then add tests up to ≥95% coverage. Keep PRs small enough to review (aim < ~800 changed lines; split big modules by package). |
| n+1 – Parity & docs | End-to-end parity suite (below), README with run/connect commands, docs. |

### Converting a module

- **Idiomatic, not transliterated.** Follow `references/idioms.md`: dataclasses/Pydantic instead of POJOs + getters/setters, modules instead of static utility classes, exceptions mapped to a small hierarchy, `pathlib`, context managers for resources, f-strings, comprehensions, `Enum`, `Protocol` for interfaces with one implementation, no `I`-prefixed ABCs, snake_case names.
- **Full type hints**; `mypy --strict` passes. Prefer the standard library; add a dependency only when the Java code used an equivalent library or it is clearly better than hand-rolling.
- **Keep the contract byte-for-byte where it is external:** JSON field names (use Pydantic aliases if Java used camelCase), HTTP status codes, MCP tool names/schemas/descriptions, CLI flags, exit codes, config property names (map `a.b.c` to `A_B_C` env vars *and* document it).
- **Numbers:** Java `int`/`long` overflow, integer division, `double` formatting (`Double.toString`) and `BigDecimal` differ from Python. Where the contract depends on them, reproduce Java's behaviour explicitly and test it.
- **Concurrency:** `ExecutorService`/`CompletableFuture` → `asyncio` for I/O-bound code (with FastAPI/`httpx`), `concurrent.futures` for CPU-bound. No unbounded queues or caches (the resilience convention).
- **Resilience (the resilience convention):** every outbound call has a timeout; retries only on recoverable errors and idempotent calls, with exponential backoff + jitter (`tenacity` or hand-rolled); token-bucket + concurrency-cap limits on every service, returning 429/503 with `Retry-After`. Use the `resiliency` skill's checklist. If the Java code lacked these, add them and note it in the design doc as an intentional difference.
- **Security:** carry over every Java control (auth, validation, size limits, log redaction, safe path handling) and don't weaken one. Never log secrets or PII. No `eval`, `exec`, `pickle` on untrusted data, `shell=True`, or `yaml.load` without `SafeLoader`.
- **Logging:** `logging` with module loggers; keep Java's log levels and don't log what Java deliberately didn't.
- **UI (the security-checks convention, WCAG 2.2 AA):** if the Java project serves a UI, the port's UI meets WCAG 2.2 AA: native elements, a label on every control, visible focus, and axe checks (Playwright or jest-axe) in CI. `pr-review` runs `ada-compatibility --diff` on it.

### Proving parity

- Every Java test has a Python counterpart (name mapping in the test's docstring: `Ports: FooTest.testBar`). List any you intentionally drop, with the reason, in the PR body.
- **Golden tests:** for anything with an external contract, run the Java build to capture real responses (HTTP, MCP tool results, CLI output) for a representative input set, commit them under `tests/golden/` together with the capture script (stdlib-only, so it can be re-run; `port-parity` re-runs it against newer Java commits), and assert the Python output matches. Generate the inputs to cover edge cases (empty, max size, invalid, unicode, error paths). For MCP servers capture over raw JSON-RPC: the `initialize` result (capabilities, serverInfo, instructions), `tools/list` (names, titles, annotations, input schemas) and `tools/call` results *and* JSON-RPC errors (unknown tool, schema-invalid arguments). Framework defaults leak into the contract — e.g. Spring AI repeats a tool's exception message on two lines and adds default annotations — capture rather than guess.
- **Capturing from the Java side is fragile — build that in:**
  - Give every reply a deadline and restart the server on a dropped reply or a dead process: the MCP Java SDK's stdio transport occasionally drops a response ("Failed to enqueue message" in its log).
  - Run Java CLI clients **one at a time**, each in its own process group (`start_new_session=True`) with a timeout, and kill the whole group on timeout. Under load a Java client can time out initializing, return from `main` without `System.exit` and hang forever on its non-daemon transport threads; it also hangs after a Spring start-up failure (missing jar, duplicate tool). Its child server JVMs keep the output pipes open, so killing only the client isn't enough.
  - Record cases whose Java output can never match by design (a Spring start-up stack trace with a timestamp) as dedicated tests, not golden cases.
- **Cross-language tests** (local-only, skipped without a JDK/jars): Python clients against the Java servers *and* Java clients against the Python servers (override the Java client's server command with `--spring.ai.mcp.client.stdio.connections.<name>.command=…` / `args[i]=…`).
- **Tests must never write to the user's home:** redirect `HOME` to a temp directory in `conftest.py` for Python processes, and give every Java process an explicit log path (`--logging.file.name=<tmp>` or `-Duser.home=<tmp>`): a JVM takes `user.home` from the password database and ignores `$HOME`.
- **Prototype the risky semantics first** (number formatting, floating-point maths, error texts) against the golden data before planning PRs, so contract surprises surface early.
- For servers, an **end-to-end test** that starts the real Python server (subprocess or ASGI test client for HTTP; stdio subprocess for MCP) and calls it as a client would.
- Differences that are bugs in the Java code: keep the Java behaviour by default, record it in the design doc's Open questions, and ask the user.

### Every PR

1. **Local gate:** `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, and the tests for what changed (`uv run pytest tests/<area> --no-cov`: the 95% gate measures the whole package, so a partial run with coverage on fails it). CI runs the full suite and the coverage gate (the coverage target). Put CI's coverage figure in the PR body; where it is under 95%, say what is uncovered and why. Run the whole suite locally (`uv run pytest`) only to reproduce what CI can't show.
2. **`pr-review <n>`** (the review threshold and security checks) takes the PR the rest of the way; don't repeat its steps here. It runs the walkthrough and an independent reviewer on PRs of 250 or more changed lines (a self-review below that), `design-patterns` and `perf-review` on 250+ line PRs, one security pass (`security-review`, plus `owasp-llm-top10` for MCP, LLM or agent code, and `compliance-check`, `digital-regulation-check` or `ada-compatibility` when the diff triggers them), `documenter` on the touched code, the findings table, green CI and the squash-merge. Nothing merges with failing CI or an open Critical, High or Medium finding. Add this parity checklist to the review (the reviewer subagent's prompt, or your own self-review):
   - Compare each converted file with its Java source (give both paths). Any behaviour difference in the public contract, error handling, numeric semantics, ordering, null/None handling or defaults?
   - Any Java test without a Python counterpart, or a ported test that asserts less than the original?
   - Any Java security or resilience control missing in the port?
   - Non-idiomatic Python (Java-isms: getters/setters, static-only classes, manual resource closing, `== None`, index loops)?
3. **`post-merge-sync <n>`** after the merge: design doc and diagram, the merged-PR counters, branch and worktree cleanup. It owns the deep-review count (the deep-review cadence) and starts `deep-review` when one is due; that review ships as its own PR through this same gate, and merges before the next module starts.

With `--no-merge`, run `pr-review <n> --no-merge` and skip step 3.

**Delegating PRs to agents:** one agent per PR (the agent-concurrency convention). A forked agent can't start subagents, so it can't run the independent review. The fork writes the code, runs the local gate, opens the PR and waits for green CI, then **stops before merging and hands back** the PR number. The parent runs steps 2 and 3 (`pr-review` may send fixes back to the fork to make).

After PR 1 merges and CI has run: set branch protection (`references/github-setup.md` §Branch protection) with the CI, CodeQL and security jobs as required checks.

After the first module PR merges (the first real code, the security-checks convention): run `compliance-check` and `digital-regulation-check` on the whole project and put their applicability tables and data maps in the design doc's Security section; run `owasp-llm-top10` on the whole project when the first MCP, LLM or agent module lands. Fixes go through a PR like any other.

## Phase 5 – Wrap up

1. **Project memory:** open questions and links up to date (`post-merge-sync` keeps the counters).
2. If the port handles sensitive data, run **`owasp-top10`** on the whole project (the security-checks convention).
3. **Hand off to `port-parity`:** check both projects' memory carries the link and the parity baseline from Phase 3, and add the capture scripts' paths as its `Golden capture` line. If golden files were re-captured from a newer Java commit during the port, move the baseline to that commit. From now on Java changes reach the port through `port-parity`, never by re-running this skill.
4. Tag `v0.1.0` (`git tag v0.1.0 && git push origin v0.1.0`) only if the user asks for a release; the release workflow publishes the wheel/sdist (and image if there is a Dockerfile).

## Final report to the user

- New project path and how to open it in IntelliJ; the GitHub repo URL and visibility.
- PRs opened/merged (number, title, merge SHA) and each one's review findings, condensed.
- Parity: Java tests ported / dropped (with reasons), golden cases passing, intentional differences, and the parity baseline recorded for `port-parity`.
- Coverage figure, CI status, security results.
- Design doc and diagram links.
- Anything waiting for the user's decision (Java bugs preserved, contract changes, settings that need a paid plan).

## References

- `references/idioms.md` — Java → Python library and idiom mapping, framework defaults.
- `references/project-layout.md` — `pyproject.toml`, layout, `.gitignore`, README skeleton.
- `references/intellij.md` — `.idea/` and `.iml` files for a uv-based Python project.
- `references/github-setup.md` — workflows, Dependabot, PR template, CODEOWNERS, SECURITY.md, repo settings, branch protection.
