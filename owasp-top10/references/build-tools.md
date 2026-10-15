# Locating build and audit tools

A missing tool on `PATH` rarely means the project can't be built. Check in this order and stop at the first that works (`<tool> --version`):

1. **Project wrappers:** `./mvnw`, `./gradlew`, `bin/rails`, `./bazelisk`. A `packageManager` field in `package.json` → `corepack`.
2. **PATH:** `mvn gradle npm pnpm yarn pip uv poetry go cargo dotnet bundle composer`.
3. **Version managers:** `~/.sdkman/candidates/*/current/bin`, `~/.asdf/shims`, `~/.nvm/versions/node/*/bin`, `~/.pyenv/shims`, `mise which <tool>`.
4. **Wrapper caches:** `~/.m2/wrapper/dists/*/*/bin/mvn`, `~/.gradle/wrapper/dists/*/*/bin/gradle`.
5. **IDE-bundled:** JetBrains, e.g. `~/.local/share/JetBrains/Toolbox/apps/*/plugins/maven-plugin/lib/maven3/bin/mvn` and `.../plugins/gradle/...` (macOS: under `~/Library/Application Support/JetBrains/Toolbox/apps/`). VS Code extensions rarely bundle build tools.
6. **Containers:** if a Dockerfile or devcontainer exists and docker/podman is present, the build may be meant to run there. Ask first.

Record the tool path you used in the report so the user can reproduce it.

## Network

First builds and most scanners download plugins or vulnerability databases. If an offline run (`mvn -o`, `--offline`) fails on a missing artifact, that's a cache gap, not a broken project. Retry online if the user allows network use; otherwise say what's missing.

## Scanners by ecosystem

Use only if installed or runnable through the build tool:

| Ecosystem | Command |
|---|---|
| Maven | `mvn dependency:tree`; `org.owasp:dependency-check-maven:check` (downloads NVD data: slow, needs network) |
| Gradle | `gradle dependencies` |
| npm / pnpm / yarn | `npm audit --omit=dev`, `pnpm audit`, `yarn npm audit` |
| Python | `pip-audit` |
| Go | `govulncheck ./...` |
| Rust | `cargo audit` |
| Ruby | `bundle audit` |
| .NET | `dotnet list package --vulnerable` |
| PHP | `composer audit` |
| Any | `osv-scanner`, `trivy fs .` |
| Secrets (incl. git history) | `gitleaks detect`, `trufflehog git file://.` |

## Unused-dependency analysis

`mvn dependency:analyze`, `npx depcheck`, `go mod why <module>`, `cargo udeps`. Treat the results as leads: these tools miss reflective, `ServiceLoader`, plugin and test-only use (see A03 in `owasp-2025.md`).
