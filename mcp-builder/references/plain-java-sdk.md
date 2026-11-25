# Plain MCP Java SDK (no Spring)

Use when the repo isn't Spring or the user wants minimal dependencies / fast startup (~0.5 s).

## Dependencies

```xml
<dependency>  <!-- core + Jackson 3 JSON mapper -->
  <groupId>io.modelcontextprotocol.sdk</groupId>
  <artifactId>mcp</artifactId>
  <version><!-- latest GA from Maven Central --></version>
</dependency>
<dependency>  <!-- slf4j-simple logs to stderr, keeping stdout clean -->
  <groupId>org.slf4j</groupId>
  <artifactId>slf4j-simple</artifactId>
  <version><!-- latest 2.0.x GA, not a 2.1 alpha --></version>
</dependency>
```

Build a runnable jar with `maven-shade-plugin` and **`ServicesResourceTransformer`** — the SDK
finds its JSON mapper through `ServiceLoader`, and the jar fails at runtime without merged
`META-INF/services` files. Also `ManifestResourceTransformer` with the main class, and exclude
`META-INF/*.SF|*.DSA|*.RSA` and `module-info.class`.

## Server

```java
McpJsonMapper json = McpJsonDefaults.getMapper();
McpSyncServer server = McpServer.sync(new StdioServerTransportProvider(json))
        .serverInfo("my-mcp-server", "0.0.1")
        .instructions("What the tools are for")
        .capabilities(ServerCapabilities.builder().tools(false).build())
        .tools(SyncToolSpecification.builder()
                .tool(Tool.builder()
                        .name("add")
                        .description("Add a and b")
                        .inputSchema(json, """
                            {"type":"object","properties":{"a":{"type":"number"},"b":{"type":"number"}},"required":["a","b"]}""")
                        .build())
                .callHandler((exchange, req) -> {
                    var args = req.arguments() == null ? Map.<String, Object>of() : req.arguments();
                    double r = ((Number) args.get("a")).doubleValue() + ((Number) args.get("b")).doubleValue();
                    return CallToolResult.builder().addTextContent(String.valueOf(r)).build();
                })
                .build())
        .build();
Runtime.getRuntime().addShutdownHook(new Thread(server::closeGracefully));
```

Errors: `CallToolResult.builder().addTextContent(msg).isError(true).build()`.

This is the handshake (2025-11-25) API. SDK 2.2+ adds the stateless 2026-07-28 API under
`io.modelcontextprotocol.modern`; it may still change in minor releases until 3.0
([release notes](https://github.com/modelcontextprotocol/java-sdk/releases)), so use it only when asked.

## Client

```java
var params = ServerParameters.builder("java").args("-jar", serverJar).build();
try (McpSyncClient client = McpClient.sync(new StdioClientTransport(params, McpJsonDefaults.getMapper()))
        .requestTimeout(Duration.ofSeconds(20)).build()) {
    client.initialize();
    client.listTools().tools().forEach(t -> System.out.println(t.name()));
    CallToolResult r = client.callTool(new CallToolRequest("add", Map.of("a", 1, "b", 2)));
}
```

## Testing a client without the real server

Write a tiny fake server class in `src/test` (same SDK, canned results) and launch it with
`ServerParameters.builder(javaBin).args("-cp", System.getProperty("java.class.path"), FakeServer.class.getName())`.
