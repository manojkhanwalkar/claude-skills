---
name: javatopython_converter
description: Convert a Java project (Maven or Gradle; plain Java, Spring Boot, Spring AI, MCP servers or clients, CLIs, libraries) into an idiomatic, behaviour-equivalent Python project. Creates a new IntelliJ project and a new GitHub repository for it, and puts the conversion through the standard process — PRs only, CI with a 95% coverage gate, CodeQL, dependency and secret scanning, Dependabot, branch protection, design doc and system diagram, a separate agent reviewing every PR (pr-review), security-review, and owasp-llm-top10 for LLM/agent code. Use when the user asks to port, convert, migrate, rewrite or translate a Java project, module or service to Python, even if they don't say "converter". Not for converting a single snippet in chat. Args - optional path to the Java project (default the current directory), optional --name <PythonProjectName> (default <JavaName>Py), optional --dir <parent> (default ~/IdeaProjects), optional --public (default private repo), optional --module <path> to convert one module only, optional --no-merge to stop with the PRs open.
---

# Java → Python converter

Turn a Java project into a new, standalone Python project that does the same thing, is
idiomatic Python, and arrives with the same engineering process as every other project:

1. A **new IntelliJ project** in its own directory.
2. A **new GitHub repository**, set up like the others (CI, security, Dependabot, branch protection).
3. The code arrives through **PRs**, each reviewed by a **separate agent**, security-checked, and merged only on green CI.
4. **Behaviour parity** with the Java original is proven by tests, not assumed.

The Java project is the source of truth and is **never modified**.

## Arguments and defaults

| Arg | Default |
|---|---|
| Java project path | current directory |
| `--name` | `<JavaProjectName>Py` (e.g. `SimpleMCPCalculator` → `SimpleMCPCalculatorPy`) |
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
- **LLM/agent code:** prompts, model calls, MCP/A2A, tools, RAG, memory → decides whether `owasp-llm-top10` applies (rule 4).

Then write the **conversion plan**:
- Java module → Python package mapping and the target layout.
- Library mapping, one line per Java dependency.
- Decisions that change shape (e.g. Spring Boot → FastAPI; Spring AI MCP → official `mcp` SDK; threads → asyncio). Apply the defaults in `references/idioms.md`; **ask the user only when a choice changes the external contract or there is no sensible default.**
- The PR sequence (Phase 4).

## Phase 2 – Design doc and system diagram (rule 2)

Look for existing ones first: `Artifact` list and the new project's memory. Then:
- **Design doc** — a Claude Doc named exactly `<name>`. Sections: Purpose, Origin (link the Java repo and commit SHA converted), Architecture, Module mapping, Library mapping, Public contract, Parity strategy, Performance/resilience/scale trade-offs (rule 6), Security, Testing and coverage, Open questions.
- **System diagram** — a Design canvas named `<name> System Diagram`: a system page plus one page per major flow.

Update both whenever a later PR changes behaviour, APIs, data or architecture.

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
6. **Project memory** for the new project (`~/.claude/projects/<encoded path of the new dir>/memory/`, the path with `/` replaced by `-`): a project memory with the Java origin (repo + SHA), the design doc and diagram links, and a **merged-PR counter** (starts at 0) for rule 5. Add the pointers to `MEMORY.md`.

## Phase 4 – Convert through PRs

Every change from here on goes through a PR (rule 1): branch from up-to-date `main`, commit, push, `gh pr create`. Recommended sequence — merge each before starting the next, so later PRs build on reviewed code:

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
- **Concurrency:** `ExecutorService`/`CompletableFuture` → `asyncio` for I/O-bound code (with FastAPI/`httpx`), `concurrent.futures` for CPU-bound. No unbounded queues or caches (rule 6).
- **Resilience (rule 6):** every outbound call has a timeout; retries only on recoverable errors and idempotent calls, with exponential backoff + jitter (`tenacity` or hand-rolled); token-bucket + concurrency-cap limits on every service, returning 429/503 with `Retry-After`. Use the `resiliency` skill's checklist. If the Java code lacked these, add them and note it in the design doc as an intentional difference.
- **Security:** carry over every Java control (auth, validation, size limits, log redaction, safe path handling) and don't weaken one. Never log secrets or PII. No `eval`, `exec`, `pickle` on untrusted data, `shell=True`, or `yaml.load` without `SafeLoader`.
- **Logging:** `logging` with module loggers; keep Java's log levels and don't log what Java deliberately didn't.

### Proving parity

- Every Java test has a Python counterpart (name mapping in the test's docstring: `Ports: FooTest.testBar`). List any you intentionally drop, with the reason, in the PR body.
- **Golden tests:** for anything with an external contract, run the Java build to capture real responses (HTTP, MCP tool results, CLI output) for a representative input set, commit them under `tests/golden/` together with the capture script (stdlib-only, so it can be re-run), and assert the Python output matches. Generate the inputs to cover edge cases (empty, max size, invalid, unicode, error paths). For MCP servers capture over raw JSON-RPC: the `initialize` result (capabilities, serverInfo, instructions), `tools/list` (names, titles, annotations, input schemas) and `tools/call` results *and* JSON-RPC errors (unknown tool, schema-invalid arguments). Framework defaults leak into the contract — e.g. Spring AI repeats a tool's exception message on two lines and adds default annotations — capture rather than guess.
- **Prototype the risky semantics first** (number formatting, floating-point maths, error texts) against the golden data before planning PRs, so contract surprises surface early.
- For servers, an **end-to-end test** that starts the real Python server (subprocess or ASGI test client for HTTP; stdio subprocess for MCP) and calls it as a client would.
- Differences that are bugs in the Java code: keep the Java behaviour by default, record it in the design doc's Open questions, and ask the user.

### Every PR, before merge

1. Local gate: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest --cov` — all green, coverage ≥ 95% (rule 7). Report coverage in the PR body; where 95% isn't reached, say what's uncovered and why.
2. **`security-review`** skill on the branch; fix what it confirms (rule 4).
3. **`owasp-llm-top10 --diff origin/main`** if the PR touches LLM/agent/MCP/A2A code; fix confirmed High and Medium.
4. **`pr-review <n>`** — the separate-agent review (rule 3). When it starts its reviewer subagent, add this parity checklist to the subagent's prompt:
   - Compare each converted file with its Java source (give both paths). Any behaviour difference in the public contract, error handling, numeric semantics, ordering, null/None handling or defaults?
   - Any Java test without a Python counterpart, or a ported test that asserts less than the original?
   - Any Java security or resilience control missing in the port?
   - Non-idiomatic Python (Java-isms: getters/setters, static-only classes, manual resource closing, `== None`, index loops)?
   `pr-review` fixes confirmed findings with tests, posts the findings table, waits for CI and squash-merges. Never merge with failing CI or an open High/Medium finding.
5. Update the design doc and diagram if the PR changed behaviour, APIs, data or architecture.
6. After the merge, increment the merged-PR counter in the project memory. When it reaches a multiple of 5, run `deep-review` on the whole codebase and ship it as its own PR through this same gate (rule 5) before starting the next module.

After PR 1 merges and CI has run: set branch protection (`references/github-setup.md` §Branch protection) with the CI, CodeQL and security jobs as required checks.

## Phase 5 – Wrap up

1. **Project memory:** bring it up to date (merged-PR count, open questions, links).
2. If the port added the project's first LLM/agent feature, run **`owasp-llm-top10`** on the whole project; if it handles sensitive data, run **`owasp-top10`** (rule 4).
3. **Deep review** (rule 5): already run after every 5th merge in Phase 4; nothing extra here unless a multiple of 5 was reached by the last merge.
4. Tag `v0.1.0` (`git tag v0.1.0 && git push origin v0.1.0`) only if the user asks for a release; the release workflow publishes the wheel/sdist (and image if there is a Dockerfile).

## Final report to the user

- New project path and how to open it in IntelliJ; the GitHub repo URL and visibility.
- PRs opened/merged (number, title, merge SHA) and each one's review findings, condensed.
- Parity: Java tests ported / dropped (with reasons), golden cases passing, intentional differences.
- Coverage figure, CI status, security results.
- Design doc and diagram links.
- Anything waiting for the user's decision (Java bugs preserved, contract changes, settings that need a paid plan).

## References

- `references/idioms.md` — Java → Python library and idiom mapping, framework defaults.
- `references/project-layout.md` — `pyproject.toml`, layout, `.gitignore`, README skeleton.
- `references/intellij.md` — `.idea/` and `.iml` files for a uv-based Python project.
- `references/github-setup.md` — workflows, Dependabot, PR template, CODEOWNERS, SECURITY.md, repo settings, branch protection.
