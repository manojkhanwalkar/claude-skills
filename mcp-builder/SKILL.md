---
name: mcp-builder
description: Create an MCP server, client or both - tools, stdio or HTTP transport, an end-to-end test and a README. Java with Spring AI by default; Python and TypeScript follow Anthropic's mcp-builder skill. Use to build an MCP server or client, or "make an MCP for X". Not for audits (owasp-llm-top10). Args - [what to wrap] [--lang java|python|typescript] [--plain-sdk] [--http] [--server-only|--client-only].
license: Apache-2.0
---

# MCP builder

Build a working MCP server and/or client, verified end to end, with a README that tells a
newcomer exactly how to start the server and connect to it.

## 0. Decide the shape (don't ask unless it truly matters)

| Question | Default |
|---|---|
| Language | Match the repo. No repo signal → **Java + Spring Boot + Spring AI** |
| Spring or plain SDK | Spring Boot if the user says "Spring" or the repo is Spring; `--plain-sdk` or no Spring in the repo → plain MCP Java SDK (see `references/plain-java-sdk.md`) |
| Transport | **stdio** (simplest; the client launches the server). `--http` → Streamable HTTP (`references/http-transport.md`). Never the old HTTP+SSE transport: deprecated since spec 2025-03-26 and Spring AI 2.0 |
| Protocol revision | The SDK default: the `initialize`-handshake revision (2025-11-25) that current clients speak. The stateless 2026-07-28 revision (`server/discover`, no sessions) only when asked or when every client supports it: a 2026-07-28-only server rejects a legacy client's `initialize` ([compatibility matrix](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning#compatibility-matrix)). Spring AI 2.1+ selects it with `spring.ai.mcp.server.protocol: MODERN` (needs MCP Java SDK 2.2+) |
| Deliverables | Server **and** a client that launches it, unless told otherwise |
| Location | New directory named as the user asked, inside the current repo if there is one; its own `mvnw` copied from the repo root if present |

Look at what the repo already does first (existing MCP modules, parent poms, Java version, test
style, CI workflow) and follow it.

## 1. Pick current versions — never from memory

Query Maven Central (or PyPI/npm) and pick the newest **GA** release, then confirm compatibility:

```bash
curl -s https://repo1.maven.org/maven2/org/springframework/ai/spring-ai-bom/maven-metadata.xml | grep '<version>' | tail
curl -s https://repo1.maven.org/maven2/io/modelcontextprotocol/sdk/mcp/maven-metadata.xml | grep '<version>' | tail
curl -s https://repo1.maven.org/maven2/org/springframework/boot/spring-boot-starter-parent/maven-metadata.xml | grep '<version>' | tail
```

Use the Spring Boot version the chosen Spring AI release is built on, and let its BOM pick the MCP SDK:

```bash
curl -s https://repo1.maven.org/maven2/org/springframework/ai/spring-ai-autoconfigure-mcp-server-common/<v>/spring-ai-autoconfigure-mcp-server-common-<v>.pom \
  | grep -A2 '<artifactId>spring-boot' | grep -m1 '<version>'
```

Last checked 2026-11: Spring AI 2.1.0 is built on Spring Boot 4.2.0 and pulls MCP Java SDK 2.2.0;
Java 25 (LTS) unless the repo uses newer. Spring AI 1.x targets Boot 3.x — don't mix majors. Spring AI 2.x moved the annotations to
`org.springframework.ai.mcp.annotation.{McpTool,McpToolParam}` (artifact `spring-ai-mcp-annotations`,
pulled in by the starters). If you're unsure of an API, resolve the dependency and `javap` the jar
rather than guessing:

```bash
./mvnw -q dependency:resolve
javap -cp ~/.m2/repository/org/springframework/ai/spring-ai-mcp-annotations/<v>/spring-ai-mcp-annotations-<v>.jar \
  'org.springframework.ai.mcp.annotation.McpTool' 'org.springframework.ai.mcp.annotation.McpTool$McpAnnotations'
unzip -p ~/.m2/repository/org/springframework/ai/spring-ai-autoconfigure-mcp-server-common/<v>/spring-ai-autoconfigure-mcp-server-common-<v>.jar \
  META-INF/spring-configuration-metadata.json | python3 -c "import json,sys;[print(p['name'],p.get('defaultValue','')) for p in json.load(sys.stdin)['properties']]"
```

## 2. Layout (Spring Boot, stdio)

```
<Project>/
  pom.xml                      # parent = spring-boot-starter-parent; imports spring-ai-bom; <modules> server THEN client
  mvnw, mvnw.cmd, .mvn/
  <name>-mcp-server/           # spring-ai-starter-mcp-server
  <name>-mcp-client/           # spring-ai-starter-mcp-client
  README.md
```

Aggregator `pluginManagement` sets `spring-boot-maven-plugin` `<finalName>${project.artifactId}</finalName>`
so jars are `target/<artifactId>.jar` (stable paths for the client config, README and tests).
List the server module first: in a reactor build each module runs all phases in turn, so the
server jar exists before the client's end-to-end test runs.

## 3. Server

```java
@Component
public class CalculatorTools {
    @McpTool(name = "divide", description = "Divide a by b. Fails if b is 0",
             annotations = @McpTool.McpAnnotations(readOnlyHint = true, destructiveHint = false,
                                                   idempotentHint = true, openWorldHint = false))
    public double divide(@McpToolParam(description = "Dividend") double a,
                         @McpToolParam(description = "Divisor (must not be 0)") double b) {
        if (b == 0) throw new IllegalArgumentException("Division by zero");  // becomes isError=true result
        return a / b;
    }
}
```

`application.yml` — **stdout is the protocol channel; anything else printed there corrupts it**:

```yaml
spring:
  main:
    web-application-type: none
    banner-mode: off
  ai:
    mcp:
      server:
        name: <name>-mcp-server
        version: 1.0.0
        stdio: true
        type: sync
        instructions: "<one line telling the model what the tools are for>"
        capabilities:          # advertise only what you implement
          prompt: false
          resource: false
          completion: false
logging:
  threshold:
    console: off               # NOT pattern.console: "" (logback errors on an empty pattern)
  file:
    name: ${user.home}/.<name>-mcp-server/server.log   # per-user, not the shared temp dir
```

The log holds tool arguments and results, so keep it in the user's home directory, not in
`java.io.tmpdir` (`/tmp` is shared on Linux, and a predictable name there can be read or
pre-created by another user). Name the path in the README.

Tool design rules:
- Tool names: short `snake_case` verbs; descriptions say what it returns and when it fails —
  the model reads them to choose tools.
- Describe every parameter. Validate inputs server-side even if the schema constrains them.
- Expected failures (bad input, not found) → throw / return an error result (`isError: true`) the
  model can act on, never crash the process; never put stack traces or secrets in it.
- Set the annotations on every tool: the defaults (spec and `@McpTool`) are `readOnlyHint=false`,
  `destructiveHint=true`, `idempotentHint=false`, `openWorldHint=true`. They are hints that clients
  treat as untrusted, not a security control: a destructive tool still needs its own checks.
- Never expose arbitrary file paths, shell commands or URLs from tool input without an allowlist;
  cap input sizes and result sizes.
- Wrap every outbound call a tool makes in a timeout (the `resiliency` skill has the checklist).
- For prompt injection through tool results, excessive agency and the rest of the LLM risks, run
  `owasp-llm-top10` on the new code rather than restating it here.

## 4. Client

```yaml
spring:
  main:
    web-application-type: none
    banner-mode: off
  ai:
    mcp:
      client:
        name: <name>-mcp-client
        type: sync
        toolcallback:
          enabled: false       # true only when feeding the tools to a ChatClient/LLM
        annotation-scanner:
          enabled: false       # no @McpSampling/@McpElicitation handlers → avoids startup warnings
        stdio:
          connections:
            <name>:
              command: java
              args:
                - -jar
                - ${<name>.server.jar:<name>-mcp-server/target/<name>-mcp-server.jar}
logging:
  level:
    root: warn
```

The starter injects `List<McpSyncClient>` (already initialized). Patterns that bit before:
- Use **`ApplicationRunner` + `getNonOptionArgs()`**, not `CommandLineRunner`, or
  `--<name>.server.jar=...` overrides get treated as positional arguments.
- Implement `ExitCodeGenerator` and `System.exit(SpringApplication.exit(SpringApplication.run(...)))`
  so the app exits (closing stdio, which stops the server) with a meaningful status.
- Put the MCP calls in a small wrapper class (`<Name>Client`) taking `McpSyncClient`, so the test
  can reuse it without Spring.
- Spring AI 2.0.x repeats the exception message on several lines in error results; show
  `text.lines().findFirst()` for errors.
- Spring Boot + Spring AI server startup is ~3–6 s, so keep client `request-timeout` at its default (20s) or higher.

## 5. Tests (required)

1. Unit tests for the tool logic (plain JUnit, no Spring context).
2. **End-to-end test in the client module** that launches the real server jar with the plain SDK
   and calls every tool, including an error case:

```java
private static final Path SERVER_JAR = Path.of("../<name>-mcp-server/target/<name>-mcp-server.jar");
@BeforeAll static void start() {
    assumeTrue(Files.exists(SERVER_JAR), "server jar not built");
    var params = ServerParameters.builder("java").args("-jar", SERVER_JAR.toString()).build();
    mcp = McpClient.sync(new StdioClientTransport(params, McpJsonDefaults.getMapper())).build();
    mcp.initialize();
}
@AfterAll static void stop() { if (mcp != null) mcp.closeGracefully(); }
```

Run `./mvnw verify` from the project root, then also run the client jar by hand (demo, one call,
error case with `echo $?`, bad usage, server-jar override from another directory). A test
passing is not enough — check the real CLI output.

Raw protocol smoke test for any stdio server that speaks the 2025-11-25 handshake (the default):

```bash
(printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'; sleep 10) | timeout 15 java -jar <server>.jar
```

A 2026-07-28 server has no handshake: every request carries its version in `_meta`. Send
`server/discover` instead of the first two lines:

```bash
'{"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"t","version":"1"},"io.modelcontextprotocol/clientCapabilities":{}}}}'
```

Every stdout line must be JSON-RPC. Any log line or banner there means a stdout leak — fix it.

Coverage: add JaCoCo (coverage.py, c8 elsewhere) with the repo's gate, or 95% line coverage in a
new project. The end-to-end test runs the server in another process, so it adds nothing to the
server's coverage: the unit tests carry it.

## 6. README (required)

Include, with copy-pasteable commands run from the project directory:
1. Diagram (`client ──(MCP over stdio)──> server`) and a module table.
2. Tool table: name, arguments, result, failure cases.
3. Prerequisites (Java version; `./mvnw` downloads Maven).
4. Build: `./mvnw package` and the jar paths it produces.
5. **Start the server**: explain that with stdio the client launches it; show the manual
   `java -jar` command plus the JSON-RPC lines to paste; say where server logs go.
6. **Use the client**: demo command, one command per tool with expected output, error example
   and exit code, how to point it at a server jar elsewhere.
7. Connect from Claude Code (`claude mcp add <name> -- java -jar "$(pwd)/.../<server>.jar"`) and
   Claude Desktop (`claude_desktop_config.json` `mcpServers` snippet).
8. How to run the tests, and a short "how it works".

If the repo has a top-level README or CI matrix listing modules, add the new project there too.

## Other languages

For `--lang python` or `--lang typescript`, follow Anthropic's `mcp-builder` skill
([anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/mcp-builder)): its
`reference/python_mcp_server.md` and `reference/node_mcp_server_v2.md` cover the SDKs, and
`reference/mcp_best_practices.md` and `reference/evaluation.md` the tool design and evals. If it
isn't installed, read those files from the repository (`gh api repos/anthropics/skills/contents/skills/mcp-builder/<file>`).
It is server-focused: for a client, use the SDK's own client guide ([official SDK guides](https://modelcontextprotocol.io/docs/sdk)).
Check its package names against the version you pick in step 1.

Same rules everywhere: nothing on stdout but protocol, log to stderr/file, current versions
from the registry, end-to-end test against the real server, README with start/connect commands.

## Finish

Ship it the way the user's and the repo's rules say, usually: a branch from an up-to-date default
branch, a commit, a PR, and `pr-review` (which runs `security-review` and `owasp-llm-top10 --diff`,
as MCP code always triggers it). If the repo has CI, add the new modules to it; a new repo gets CI
with build, tests and the coverage gate, plus the GitHub security and Dependabot setup the user's
rules list. Never push or merge without those steps.

Report: what was created (paths), the exact verification you ran and its results, versions
chosen, the protocol revision and transport, the PR, and any limitation.
