# Streamable HTTP transport (instead of stdio)

Use when the server must run as a long-lived service, be shared by several clients, or run remotely.

## Spring AI server

- Dependency: `spring-ai-starter-mcp-server-webmvc` (or `-webflux`) instead of `spring-ai-starter-mcp-server`.
- Config: remove `stdio: true` and `web-application-type: none`; set
  `spring.ai.mcp.server.protocol: streamable` (default in 2.x; `MODERN` for the stateless 2026-07-28
  revision, Spring AI 2.1+; never the deprecated `SSE`), `server.port` and
  `server.address: 127.0.0.1` (Spring Boot otherwise listens on all interfaces).
  The endpoint is `spring.ai.mcp.server.streamable-http.mcp-endpoint` (default `/mcp`).

  ```yaml
  server:
    address: 127.0.0.1
    port: 8080
  spring:
    ai:
      mcp:
        server:
          protocol: streamable
  ```
- Console logging is fine again (stdout isn't the protocol).
- Security: the Spring AI starters apply no authentication and no `Origin` check of their own
  ([Spring AI reference](https://docs.spring.io/spring-ai/reference/api/mcp/mcp-server-boot-starter-docs.html)),
  so add them. An unauthenticated MCP endpoint is remote code execution for whatever the tools can do.
  The spec's rules ([Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http#security-%26-endpoint),
  [Authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)):
  - **Local:** bind to `127.0.0.1` and check it after starting the server (`ss -ltnp` on Linux,
    `lsof -nP -iTCP -sTCP:LISTEN` on macOS).
  - **Origin:** a request whose `Origin` header is present and not on an allowlist gets 403 (DNS
    rebinding). A filter does it, or [MCP Security](https://github.com/spring-ai-community/mcp-security).
  - **Remote:** the server is an OAuth 2.1 resource server (Spring Security `oauth2ResourceServer`).
    It serves RFC 9728 metadata at `/.well-known/oauth-protected-resource`, answers a missing or bad
    token with 401 and `WWW-Authenticate: Bearer resource_metadata="…", scope="…"`, and a missing
    scope with 403 `error="insufficient_scope"`. It accepts only tokens whose audience is its own
    canonical URL (RFC 8707) and never passes a client's token on to other services.
  - **Limits:** cap the request body size and rate-limit per user (429 with `Retry-After`), with
    timeouts on every downstream call (the `resiliency` skill).
  - Test each of these: a request without a token, one with the wrong audience, a bad `Origin`.
  stdio servers don't use OAuth: they read credentials from the environment.
- Clients connect to `127.0.0.1`, not `localhost`: `localhost` can resolve to `::1` first, where nothing listens.

## Spring AI client

```yaml
spring.ai.mcp.client.streamable-http.connections.<name>.url: http://127.0.0.1:8080
```
(Starter `spring-ai-starter-mcp-client` covers HTTP via the JDK HttpClient; `-webflux` variant for WebClient.)

## README changes

"Start the server" now really means starting it (`java -jar server.jar`, wait for the port), then
running the client in another terminal. Claude Code: `claude mcp add --transport http <name> http://127.0.0.1:8080/mcp`.

## Plain Java SDK

Server: `HttpServletStreamableServerTransportProvider` in a servlet container (bind its connector to `127.0.0.1`).
Client: `HttpClientStreamableHttpTransport.builder("http://127.0.0.1:8080").build()`.
