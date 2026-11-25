# OWASP LLM (2026) and Agentic (2026) Top 10, plus MCP — Audit Checklist

Per ID: what to look for, grep starting points, typical fixes, and false positives. Grep hits are leads only: read the code and trace the path.

Sources (OWASP GenAI Security Project, [genai.owasp.org](https://genai.owasp.org/)):
- [Top 10 for LLM Applications 2026](https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/), published 2026-08-04 ([entries](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/tree/main/2026/final)).
- [Top 10 for Agentic Applications for 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/), published 2025-12-09.
- MCP: the [MCP Top 10](https://owasp.org/www-project-mcp-top-10/) (beta, IDs `MCP01:2025`–`MCP10:2025`), [A Practical Guide for Secure MCP Server Development](https://genai.owasp.org/resource/a-practical-guide-for-secure-mcp-server-development/) (2026-02-16), and the MCP specification's [Security Best Practices](https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices).

**2025 → 2026 LLM IDs.** Older reports, issues and review rules may cite the 2025 numbers. Report with the 2026 IDs, and map old ones with this table:

| 2025 | 2026 |
|---|---|
| LLM01 Prompt Injection | LLM01 Prompt Injection (now also cross-modal: image, audio, video) |
| LLM02 Sensitive Information Disclosure | LLM02 (unchanged) |
| LLM03 Supply Chain | LLM04 Supply Chain |
| LLM04 Data and Model Poisoning | LLM05 Data and Model Poisoning (now also fine-tuning subversion) |
| LLM05 Improper Output Handling | LLM10 Improper Output Handling (now also insecure generated code) |
| LLM06 Excessive Agency | LLM03 Excessive Agency |
| LLM07 System Prompt Leakage | LLM08 Hidden Context Exposure (broader: tool schemas, retrieved policy text) |
| LLM08 Vector and Embedding Weaknesses | LLM09 Vector and Embedding Weaknesses |
| LLM09 Misinformation | LLM07 Misinformation |
| LLM10 Unbounded Consumption | LLM06 Unbounded Consumption |

## Contents
- Finding the AI surface
- LLM01 Prompt Injection
- LLM02 Sensitive Information Disclosure
- LLM03 Excessive Agency
- LLM04 Supply Chain
- LLM05 Data and Model Poisoning
- LLM06 Unbounded Consumption
- LLM07 Misinformation
- LLM08 Hidden Context Exposure
- LLM09 Vector and Embedding Weaknesses
- LLM10 Improper Output Handling
- ASI01 Agent Goal Hijack
- ASI02 Tool Misuse and Exploitation
- ASI03 Identity and Privilege Abuse
- ASI04 Agentic Supply Chain
- ASI05 Unexpected Code Execution
- ASI06 Memory and Context Poisoning
- ASI07 Insecure Inter-Agent Communication
- ASI08 Cascading Failures
- ASI09 Human-Agent Trust Exploitation
- ASI10 Rogue Agents
- MCP servers and clients (M1–M9)

---

## Finding the AI surface

`anthropic|openai|bedrock|vertex|gemini|ollama|mistral|cohere|huggingface` ·
`ChatModel|ChatClient|AiServices|@Tool|@McpTool|McpServer|McpClient|tool_use|function_call|tools=|registerTool` ·
`system(Message|Prompt)|SystemMessage|systemPrompt|prompt_template|PromptTemplate|messages\.append` ·
`EmbeddingStore|VectorStore|embedding|retriever|similarity|pinecone|pgvector|chroma|faiss` ·
`ChatMemory|MessageWindow|conversation|history|memory` ·
`/mcp|a2a|AgentCard|tasks/send|message/send` ·
`guardrail|moderation|sanitiz|redact|profan|jailbreak|injection`

MCP specifically: `Origin|allowedOrigins|0\.0\.0\.0|bind|host:` · `aud|audience|resource=|issuer|jwk|introspect` · `Authorization|Bearer|forward|passthrough|getHeader\("Authorization"\)` · `readOnlyHint|destructiveHint|annotations|listChanged|tools/list` · `client_id|redirect_uri|consent|state=|register` · `Mcp-Session-Id|sessionId|handle`.

Also look for placeholders such as "LLM goes here": a seam where a model will be plugged in is reviewed as though the model were there.

---

## LLM01 Prompt Injection

**Look for**
- User text joined into the system prompt or the instructions, rather than kept in a separate, clearly delimited user turn.
- Indirect input (documents, web pages, emails, tool results, MCP server output, retrieved chunks, memory, issue titles) placed in the prompt without marking it as untrusted data.
- Images, audio or video passed to a multimodal model with no screening: instructions hide in pixels, OCR-able text or audio tracks.
- No input screening at all, or screening that matches raw text only: defeated by look-alike letters, zero-width characters, leetspeak, base64, hex or Morse, and by role markers (`<|system|>`, `[INST]`, `<<SYS>>`, `### system`, `assistant:`).
- Delimiters the user can close (a `</user_message>` typed by the user ends the block early).
- A model's "refusal" relied on as the only control in front of a consequential action.

**Fix**
- Keep instructions and data apart: a fixed system prompt, and untrusted text in tagged blocks the prompt says are data. Strip or refuse closing tags and role markers.
- Normalise (NFKC, drop invisible characters, fold homoglyphs and leetspeak) before every pattern check.
- Screen at every modality boundary: OCR images and transcribe audio, then apply the text checks.
- Screen the input deterministically, and with a classifier when the stakes are high.
- Allow-list topics where the product is narrow.
- Put every consequential action behind a check outside the model (LLM03).

**False positives:** a text-only answer rendered as text, with no tools and no other user's data in reach. That is still worth a Low finding for off-topic or brand risk.

## LLM02 Sensitive Information Disclosure

**Look for**
- PII, secrets or other users' data in prompts, memory, logs, traces, analytics or fine-tuning sets.
- Conversation memory or caches keyed by something a user controls, or shared across users.
- Output not checked for identifiers (SSNs, card or account numbers, emails, phones, API keys).
- Full prompts and completions logged by default (SDK `logRequests`/`logResponses`, debug logs, tracing).
- Data sent to a third-party model without minimising it (whole records where a few fields would do).

**Fix:** minimise what goes in; redact identifiers in both directions; key memory on the authenticated identity on the server side; turn off prompt logging or redact it; set data-retention terms with the provider. PII security controls in general belong to `compliance-check`.

## LLM03 Excessive Agency

**Look for** tools with more power than the feature needs (generic "run SQL", "HTTP GET any URL", "write any file", shell), tools that act with a service account instead of the user's identity, consequential actions (payments, deletions, emails, permission changes) with no confirmation, and autonomous loops with no step or cost limit.

**Fix:** least functionality (few, narrow, purpose-built tools; no open-ended ones); least privilege (run in the user's context, scoped tokens); human confirmation for consequential or irreversible actions; complete mediation (every tool call authorised outside the model); monitor tool use; rate and step limits. Tool annotations (`readOnlyHint`, `destructiveHint`) describe a tool to clients; they are not a control (M5).

## LLM04 Supply Chain

**Look for** unpinned model names or versions (`latest`), models or adapters downloaded at runtime from unverified sources, unsigned model artifacts promoted between environments with no provenance check, `pickle` or `torch.load` on untrusted weights (`weights_only=False`), unpinned SDKs and plugins, third-party prompt hubs, and provider terms that allow training on your data. MCP servers and tool registries are covered by ASI04 and M6.

**Fix:** pin model IDs and SDK versions; verify hashes and signatures at every promotion; prefer safetensors; vet plugins; keep an inventory (an AI-BOM).

## LLM05 Data and Model Poisoning

**Look for**
- Fine-tuning or RAG ingestion from sources users can write to (tickets, wikis, uploads, web crawls) with no review or provenance.
- Fine-tuning jobs whose data or hyperparameters a user can influence.
- Feedback loops: user ratings or conversations fed back into training or memory unchecked.

**Fix:** keep provenance per document; review or gate writes; keep ingestion separate from serving; evaluate a tuned model before promoting it; be able to roll back.

## LLM06 Unbounded Consumption

**Look for** no limit on input length, output tokens, reasoning or thinking tokens, conversation length, requests per user, concurrent requests, or tool-loop steps; no spending cap per user or tenant (denial of wallet); large multimodal inputs accepted unbounded; memory or caches that grow without bound; no timeout on model calls; retries that multiply cost; unthrottled bulk querying that would let someone distil the model.

**Fix:** cap input, `max_tokens` and thinking budgets; trim history; per-user rate limits and a concurrency cap; hard spending caps with alerts; timeouts; bounded caches (LRU, TTL); a circuit breaker on agent loops. Timeouts, retries and request limits in general belong to `resiliency`.

## LLM07 Misinformation

**Look for** answers presented as fact in high-stakes areas (financial, medical, legal) with no grounding, no source, and no disclaimer; and promises the product must not make ("guaranteed", "100%").

**Fix:** ground answers in supplied data and say when it is missing; cite sources; add domain disclaimers; block or soften promise language; keep a human in the loop for decisions.

## LLM08 Hidden Context Exposure

Formerly System Prompt Leakage. Hidden context is everything the model sees and the user doesn't: the system prompt, developer instructions, retrieved policy text, tool and function schemas. Assume all of it is discoverable.

**Look for**
- Secrets, keys, tokens or connection strings in any hidden context.
- Authorisation, privilege separation or content policy that depends on the hidden context staying secret.
- Internal rules, refusal criteria, role descriptions or workflow logic that would help an attacker plan an injection.
- No check for answers that echo the instructions.

**Severity** (from the 2026 entry): Info when nothing sensitive is in it and nothing relies on its secrecy; Medium for rules that meaningfully aid an attacker; High for embedded credentials or reliance on secrecy for authorisation or policy; Critical when disclosure chains to code execution, broad exfiltration or privilege escalation.

**Fix:** keep secrets and authorisation out of the context (enforce them in code); deterministic guardrails rather than instructions; add a canary to the instructions and block answers that contain it or the prompt's delimiters.

## LLM09 Vector and Embedding Weaknesses

**Look for**
- One vector index shared across tenants or users with no filter on retrieval.
- Access control checked at ingestion but not at query time.
- Embeddings of sensitive text stored without the source's protections (embeddings can be inverted).
- A semantic cache shared across users: one user's cached answer served to another, or poisoned.
- Retrieved chunks trusted as instructions (LLM01).

**Fix:** a permission filter on every retrieval (the tenant and user from the session, never from the prompt); separate indexes or trust tiers where needed; semantic caches keyed per tenant; the same retention and encryption as the source data.

## LLM10 Improper Output Handling

**Look for** model output that reaches a sink without encoding or validation: `innerHTML`, `dangerouslySetInnerHTML`, `v-html`, Markdown rendered to HTML (watch image links and link previews, which exfiltrate through their URLs), SQL strings, shell commands, `eval`, file paths, URLs fetched by the server (SSRF), redirects, email headers, arguments passed to other tools, and generated code compiled, merged or deployed without review or scanning.

**Fix:** treat output as untrusted user input. Encode it for its sink (`textContent`, parameterised queries); validate it against a schema; allow-list URLs and commands; disable auto-fetching of remote images and previews in rendered output; run generated code through the same review and SAST as human code.

---

## ASI01 Agent Goal Hijack

The agentic form of LLM01. Instructions planted in a document, page, email, ticket or tool result redirect the agent's goal or plan.

**Look for:** agents that read external content and then act; plans that the content can rewrite; no check that each action still serves the user's original request.

**Fix:** keep the user's intent as a fixed record outside the context; check every planned action against it and against an allow-list; tag external content as data; ask for confirmation when the plan changes.

## ASI02 Tool Misuse and Exploitation

**Look for** legitimate tools used in harmful ways: chaining, over-broad arguments (wildcards, mass deletes), ambiguous or poisoned tool descriptions (M4), tool results trusted blindly, and no rate or scope limit per tool.

**Fix:** narrow tool schemas (enums, bounds, no free-form commands); validate arguments server-side; limit per tool and per session; log every call; dry-run modes for destructive tools.

## ASI03 Identity and Privilege Abuse

**Look for**
- Agents that act under a shared service identity rather than the user's.
- Credentials kept in the context or in memory.
- Privileges inherited across delegation steps (a sub-agent that gets the parent's full token).
- Missing audience or scope checks on tokens agents present; tokens passed through (M1).

**Fix:** a distinct identity per agent; delegated, scoped, short-lived tokens bound to the user and the audience (RFC 8707); credentials kept outside the model's context; authorisation re-checked at every hop.

## ASI04 Agentic Supply Chain

**Look for** tools, MCP servers, plugins, prompts or agent cards loaded at runtime from third parties without pinning or verification; and tool descriptions that a server can change after approval ("rug pull", M6).

**Fix:** pin and verify; an allow-list of servers; re-approve when a tool's description or schema changes; isolate third-party tools.

## ASI05 Unexpected Code Execution

**Look for** code that the agent writes and then runs: `eval`, `exec`, interpreters, notebooks, shell tools; generated SQL or scripts run with real credentials; no sandbox.

**Fix:** avoid it where possible. Otherwise use a sandbox (container or VM, no network, read-only filesystem, resource limits), static checks before running, a review step, and separate credentials.

## ASI06 Memory and Context Poisoning

**Look for**
- Memory written from untrusted input and read back as trusted context.
- Memory shared across users or sessions.
- No expiry; no way to inspect or purge memory.
- Model output saved to memory unfiltered, so one successful injection persists.

**Fix:** store only guard-checked content (filtered input and output); scope memory to the authenticated user and session; TTL and size bounds; provenance on entries; purge at logout; never store secrets.

## ASI07 Insecure Inter-Agent Communication

**Look for** agent-to-agent calls (A2A, MCP, queues, HTTP) with no authentication, no TLS, no message integrity, and no replay protection; agent cards or capabilities fetched and trusted without verification; one agent's output fed to another as instructions.

**Fix:** mutual authentication (mTLS or signed tokens with an audience); TLS; signed messages with nonces or expiry; schema-checked messages; treat peer output as data.

## ASI08 Cascading Failures

**Look for** one agent's error or poisoned output spreading through a chain or swarm; no timeouts, circuit breakers or limits between agents; retries that amplify load; no isolation between workflows.

**Fix:** timeouts and bounded retries with backoff and jitter on every hop; circuit breakers; output validation at each hand-off; bulkheads; fail closed.

## ASI09 Human-Agent Trust Exploitation

**Look for** agents that persuade users into acting, with overconfident language, false authority or urgency; consequential actions approved by a human shown a summary the agent wrote; answers presented as professional advice.

**Fix:** show the raw facts and the exact action before approval; disclaimers and a "verify independently" message in high-stakes areas; no dark patterns; make it easy to decline.

## ASI10 Rogue Agents

**Look for** agents whose behaviour drifts from their purpose (misaligned objectives, reward hacking, collusion) with no monitoring; no kill switch; no record of what they did.

**Fix:** behavioural monitoring against a baseline; immutable audit logs of actions; a kill switch and quarantine; scoped, expiring permissions; periodic re-attestation.

---

## MCP servers and clients (M1–M9)

Run this section whenever the scope has an MCP server, client or proxy. Each check cites the spec and the IDs it maps to; report a finding under those IDs with the check number in the title (for example "ASI03 / MCP01 — M1 token passthrough"). Spec links are to revision 2026-07-28; the same rules hold in 2025-11-25 unless noted.

**M1 Token passthrough and audience** (ASI03, LLM03; MCP01, MCP02, MCP07). [Authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization), [Token Passthrough](https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices#token-passthrough).
- Look for: an HTTP server that accepts any valid JWT from the issuer without checking `aud` is its own canonical URL; a client that requests tokens without the `resource` parameter (RFC 8707); a server that forwards the client's `Authorization` header or token to a downstream API; long-lived or broad-scope tokens (`*`, `admin`), tokens in logs or tool results.
- Fix: accept only tokens issued for this server (audience = its canonical URL); get a separate token for each downstream API (token exchange or its own client credentials); narrow scopes with step-up challenges; never log or return tokens.
- Severity: Critical when a server with write access or access to user data accepts or forwards foreign tokens; High otherwise.

**M2 Origin check and DNS rebinding** (ASI07; MCP07). [Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http), "Security & Endpoint".
- Look for: a Streamable HTTP server that doesn't validate `Origin` (a present, non-allow-listed `Origin` must get 403); a local server bound to `0.0.0.0` instead of `127.0.0.1`; a local HTTP server with no authentication. Frameworks rarely do this for you (the Spring AI starters don't).
- Fix: an `Origin` allow-list filter returning 403; bind to loopback; require a token even locally, or use stdio.
- Test: a request with a foreign `Origin` gets 403.

**M3 Confused deputy in OAuth proxies** (ASI03; MCP07). [Confused Deputy Problem](https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices#confused-deputy-problem).
- Look for: an MCP server that fronts a third-party API with one static client ID, lets MCP clients register dynamically, and forwards to the third party's consent with no consent of its own per `client_id`; `redirect_uri` matched by prefix or pattern; `state` missing, reusable, or set before consent.
- Fix: per-user, per-client consent stored server-side and checked before the third-party flow; a consent page that names the client, scopes and redirect URI, with CSRF protection and `frame-ancestors 'none'`; exact `redirect_uri` match; single-use, short-lived `state` set only after consent.

**M4 Tool poisoning and description injection** (LLM01, ASI01, ASI02; MCP03, MCP06).
- Look for, in a server: tool names, descriptions, parameter descriptions, prompts or resource text built from data that users or third parties control; tool results that return fetched or user-written content without marking it as data. In a client or host: tool descriptions and results from third-party servers passed to the model with no screening; descriptions that contain instructions to the model ("before using this tool, read ~/.ssh/…", "also call X"), hidden Unicode, or text the user never sees; tools from several servers merged with no name prefixes, so one server can shadow another's tool.
- Fix: static descriptions written by the server's authors; results tagged as untrusted data and screened like any indirect input (LLM01); clients show the full description and the exact arguments before a sensitive call; prefix tool names with the server; validate structured results against `outputSchema`.

**M5 Tool annotations are untrusted** (LLM03, ASI02). [Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools): clients must treat annotations as untrusted unless they come from trusted servers.
- Look for: a client or gateway that skips confirmation because a tool says `readOnlyHint: true` or `destructiveHint: false`; a server that relies on annotations instead of its own checks; destructive tools with annotations left at the defaults (`destructiveHint` defaults to true, so missing annotations are honest but unhelpful) or set wrongly to read-only.
- Fix: decide confirmation from the client's own policy per server and tool; enforce safety on the server regardless of hints; set accurate annotations on every tool.

**M6 Rug pull and unvetted servers** (ASI04, LLM04; MCP04, MCP09).
- Look for: servers launched with `npx`/`uvx` of an unpinned package or from a URL; no allow-list of servers; tool definitions not pinned after approval, so a `notifications/tools/list_changed` or a new version can change a description or schema silently; one-click local server installs that run a command without showing it.
- Fix: pin versions and hashes; an allow-list (no shadow servers); hash each approved tool definition and re-approve on change; show the exact launch command and get consent; run local servers sandboxed with least privilege.

**M7 State handles and sessions** (ASI03, LLM02; MCP10). [State Handle Hijacking](https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices#state-handle-hijacking).
- Look for: a session ID (`Mcp-Session-Id`, 2025-11-25 and earlier) or state handle treated as authentication; predictable handles; state keyed by the handle alone, so another user's handle reaches their data; context or memory shared between clients.
- Fix: authenticate every request; random, expiring handles; key state on `<user id from the verified token>:<handle>` and reject a handle presented by anyone else.

**M8 SSRF and unsafe URLs in clients** (LLM10, ASI05; MCP05). [SSRF](https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices#server-side-request-forgery-ssrf), [OAuth Authorization URL Validation](https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices#oauth-authorization-url-validation).
- Look for: a server-side MCP client that follows `resource_metadata`, authorization-server or token-endpoint URLs from a server without blocking private, loopback and link-local ranges (`169.254.169.254`); authorization URLs opened through a shell or with `javascript:`/`data:`/`file:` schemes allowed; server tools that fetch a URL or open a path from tool input.
- Fix: HTTPS only (loopback excepted in development); block private ranges with a vetted library or an egress proxy, and re-check redirects; allow only `https` (and loopback `http`) and open URLs without a shell; allow-list fetch targets and paths in tools.

**M9 Tool-call limits, audit and errors** (LLM06, ASI08, ASI10; MCP08). [Tools, Security Considerations](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#security-considerations).
- Look for: no rate limit on tool calls; no timeout on tool calls (client) or on the outbound calls a tool makes (server); no audit log of tool calls (who, which tool, arguments with secrets redacted, outcome); stack traces, tokens or internal URLs in error results; sensitive parameters marked `x-mcp-header` (headers are visible to intermediaries).
- Fix: per-client rate and concurrency limits; timeouts (the `resiliency` skill); an audit log; generic `isError` messages; keep secrets and PII out of mirrored headers.
