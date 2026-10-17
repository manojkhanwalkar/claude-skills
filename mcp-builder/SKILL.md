---
name: mcp-builder
description: Create a new MCP (Model Context Protocol) server, client, or server+client pair - scaffold the project, implement tools, wire the transport (stdio by default, or Streamable HTTP), add an end-to-end test that launches the real server, and write a README with run and connect commands. Defaults to Java with Spring Boot + Spring AI MCP starters; also covers the plain MCP Java SDK and points to the Python/TypeScript SDKs. Use whenever the user asks to build, scaffold, wrap something as, or add tools to an MCP server or MCP client, expose an API/library/CLI to Claude or another LLM over MCP, or "make an MCP for X", even if they don't say "server" or "client" explicitly. Args - free-text description of what to wrap, optional --lang java|python|typescript, optional --plain-sdk (Java without Spring), optional --http (Streamable HTTP instead of stdio), optional --server-only / --client-only.
---

# MCP builder

Build a working MCP server and/or client, verified end to end, with a README that tells a
newcomer exactly how to start the server and connect to it.

## 0. Decide the shape (don't ask unless it truly matters)

| Question | Default |
|---|---|
| Language | Match the repo. No repo signal → **Java + Spring Boot + Spring AI** |
| Spring or plain SDK | Spring Boot if the user says "Spring" or the repo is Spring; `--plain-sdk` or no Spring in the repo → plain MCP Java SDK (see `references/plain-java-sdk.md`) |
| Transport | **stdio** (simplest; the client launches the server). `--http` → Streamable HTTP (`references/http-transport.md`) |
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

Known-good combination (Oct 2026): **Spring Boot 4.1.x + Spring AI 2.0.1** (pulls MCP Java SDK 2.0.0),
Java 25. Spring AI 1.x targets Boot 3.x — don't mix majors. Spring AI 2.x moved the annotations to
`org.springframework.ai.mcp.annotation.{McpTool,McpToolParam}` (artifact `spring-ai-mcp-annotations`,
pulled in by the starters). If you're unsure of an API, resolve the dependency and `javap` the jar
rather than guessing:

```bash
./mvnw -q dependency:resolve
javap -cp ~/.m2/repository/org/springframework/ai/spring-ai-mcp-annotations/<v>/*.jar org.springframework.ai.mcp.annotation.McpTool
unzip -p ~/.m2/repository/org/springframework/ai/spring-ai-autoconfigure-mcp-server-common/<v>/*.jar \
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
    @McpTool(name = "divide", description = "Divide a by b. Fails if b is 0")
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
    name: ${java.io.tmpdir}/<name>-mcp-server.log
```

Tool design rules:
- Tool names: short `snake_case` verbs; descriptions say what it returns and when it fails —
  the model reads them to choose tools.
- Describe every parameter. Validate inputs server-side even if the schema constrains them.
- Expected failures (bad input, not found) → throw / return an error result, never crash the process.
- Read-only tools: set annotations (`readOnlyHint`, `destructiveHint=false`, `idempotentHint`).
- Never expose arbitrary file paths, shell commands or URLs from tool input without an allowlist.

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
- Spring AI 2.0.1 repeats the exception message on several lines in error results; show
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

Raw protocol smoke test for any stdio server:

```bash
(printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'; sleep 10) | timeout 15 java -jar <server>.jar
```

Every stdout line must be JSON-RPC. Any log line or banner there means a stdout leak — fix it.

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

- **Python**: official `mcp` SDK, `FastMCP` (`@mcp.tool()` decorators, `mcp.run()` for stdio);
  client via `mcp.client.stdio.stdio_client` + `ClientSession`. Use `uv` for the project.
- **TypeScript**: `@modelcontextprotocol/sdk`, `McpServer` + `server.registerTool(...)` with zod
  schemas, `StdioServerTransport`; client `Client` + `StdioClientTransport`.

Same rules everywhere: nothing on stdout but protocol, log to stderr/file, current versions
from the registry, end-to-end test against the real server, README with start/connect commands.

## Finish

Report: what was created (paths), the exact verification you ran and its results, versions
chosen, and any limitation. Commit only if the user asks.
