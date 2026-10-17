# Streamable HTTP transport (instead of stdio)

Use when the server must run as a long-lived service, be shared by several clients, or run remotely.

## Spring AI server

- Dependency: `spring-ai-starter-mcp-server-webmvc` (or `-webflux`) instead of `spring-ai-starter-mcp-server`.
- Config: remove `stdio: true` and `web-application-type: none`; set
  `spring.ai.mcp.server.protocol: streamable` (default in 2.x) and `server.port`.
  The endpoint is `spring.ai.mcp.server.streamable-http.mcp-endpoint` (default `/mcp`).
- Console logging is fine again (stdout isn't the protocol).
- Security: bind to localhost unless told otherwise; validate `Origin`; for anything remote,
  add authentication (Spring Security / OAuth2 resource server) — an unauthenticated MCP endpoint
  is remote code execution for whatever the tools can do.

## Spring AI client

```yaml
spring.ai.mcp.client.streamable-http.connections.<name>.url: http://localhost:8080
```
(Starter `spring-ai-starter-mcp-client` covers HTTP via the JDK HttpClient; `-webflux` variant for WebClient.)

## README changes

"Start the server" now really means starting it (`java -jar server.jar`, wait for the port), then
running the client in another terminal. Claude Code: `claude mcp add --transport http <name> http://localhost:8080/mcp`.

## Plain Java SDK

Server: `HttpServletStreamableServerTransportProvider` in a servlet container.
Client: `HttpClientStreamableHttpTransport.builder("http://localhost:8080").build()`.
