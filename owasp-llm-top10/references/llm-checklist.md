# OWASP LLM (2025) and Agentic (2026) Top 10 — Audit Checklist

Per ID: what to look for, grep starting points, typical fixes, and false positives. Grep hits are leads only: read the code and trace the path. Sources: [OWASP Gen AI Security Project](https://genai.owasp.org/) (LLM Top 10 2025; Top 10 for Agentic Applications, December 2025).

## Contents
- Finding the AI surface
- LLM01 Prompt Injection
- LLM02 Sensitive Information Disclosure
- LLM03 Supply Chain
- LLM04 Data and Model Poisoning
- LLM05 Improper Output Handling
- LLM06 Excessive Agency
- LLM07 System Prompt Leakage
- LLM08 Vector and Embedding Weaknesses
- LLM09 Misinformation
- LLM10 Unbounded Consumption
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

---

## Finding the AI surface

`anthropic|openai|bedrock|vertex|gemini|ollama|mistral|cohere|huggingface` ·
`ChatModel|ChatClient|AiServices|@Tool|@McpTool|McpServer|tool_use|function_call|tools=|registerTool` ·
`system(Message|Prompt)|SystemMessage|systemPrompt|prompt_template|PromptTemplate|messages\.append` ·
`EmbeddingStore|VectorStore|embedding|retriever|similarity|pinecone|pgvector|chroma|faiss` ·
`ChatMemory|MessageWindow|conversation|history|memory` ·
`/mcp|a2a|AgentCard|tasks/send|message/send` ·
`guardrail|moderation|sanitiz|redact|profan|jailbreak|injection`

Also look for placeholders such as "LLM goes here": a seam where a model will be plugged in is reviewed as though the model were there.

---

## LLM01 Prompt Injection

**Look for**
- User text joined into the system prompt or the instructions, rather than kept in a separate, clearly delimited user turn.
- Indirect input (documents, web pages, emails, tool results, retrieved chunks, memory) placed in the prompt without marking it as untrusted data.
- No input screening at all, or screening that matches raw text only: defeated by look-alike letters, zero-width characters, leetspeak, base64, hex or Morse, and by role markers (`<|system|>`, `[INST]`, `<<SYS>>`, `### system`, `assistant:`).
- Delimiters the user can close (a `</user_message>` typed by the user ends the block early).
- A model's "refusal" relied on as the only control in front of a consequential action.

**Fix**
- Keep instructions and data apart: a fixed system prompt, and untrusted text in tagged blocks the prompt says are data. Strip or refuse closing tags and role markers.
- Normalise (NFKC, drop invisible characters, fold homoglyphs and leetspeak) before every pattern check.
- Screen the input deterministically, and with a classifier when the stakes are high.
- Allow-list topics where the product is narrow.
- Put every consequential action behind a check outside the model (LLM06).

**False positives:** a text-only answer rendered as text, with no tools and no other user's data in reach. That is still worth a Low finding for off-topic or brand risk.

## LLM02 Sensitive Information Disclosure

**Look for**
- PII, secrets or other users' data in prompts, memory, logs, traces, analytics or fine-tuning sets.
- Conversation memory or caches keyed by something a user controls, or shared across users.
- Output not checked for identifiers (SSNs, card or account numbers, emails, phones, API keys).
- Full prompts and completions logged by default (SDK `logRequests`/`logResponses`, debug logs, tracing).
- Data sent to a third-party model without minimising it (whole records where a few fields would do).

**Fix:** minimise what goes in; redact identifiers in both directions; key memory on the authenticated identity on the server side; turn off prompt logging or redact it; set data-retention terms with the provider.

## LLM03 Supply Chain

**Look for** unpinned model names or versions (`latest`), models or adapters downloaded at runtime from unverified sources, `pickle` or `torch.load` on untrusted weights (`weights_only=False`), unpinned SDKs and plugins, and third-party prompt hubs.

**Fix:** pin model IDs and SDK versions; verify hashes and signatures; prefer safetensors; vet plugins and MCP servers; keep an inventory (an AI-BOM).

## LLM04 Data and Model Poisoning

**Look for**
- Fine-tuning or RAG ingestion from sources users can write to (tickets, wikis, uploads, web crawls) with no review or provenance.
- Feedback loops: user ratings or conversations fed back into training or memory unchecked.

**Fix:** keep provenance per document; review or gate writes; keep ingestion separate from serving; be able to roll back.

## LLM05 Improper Output Handling

**Look for** model output that reaches a sink without encoding or validation: `innerHTML`, `dangerouslySetInnerHTML`, `v-html`, Markdown rendered to HTML (watch image links, which exfiltrate through their URLs), SQL strings, shell commands, `eval`, file paths, URLs fetched by the server (SSRF), redirects, email headers, and arguments passed to other tools.

**Fix:** treat output as untrusted user input. Encode it for its sink (`textContent`, parameterised queries); validate it against a schema; allow-list URLs and commands; disable remote images in rendered Markdown.

## LLM06 Excessive Agency

**Look for** tools with more power than the feature needs (generic "run SQL", "HTTP GET any URL", "write any file", shell), tools that act with a service account instead of the user's identity, consequential actions (payments, deletions, emails, permission changes) with no confirmation, and autonomous loops with no step or cost limit.

**Fix:** least functionality (narrow, purpose-built tools); least privilege (run as the user, scoped tokens); human confirmation for consequential or irreversible actions; tool argument validation outside the model; rate and step limits. Annotate tools as read-only or destructive (for example MCP `readOnlyHint` and `destructiveHint`).

## LLM07 System Prompt Leakage

**Look for**
- Secrets, keys, internal URLs, role rules or business rules in the system prompt that would hurt if seen.
- Security that depends on the prompt staying secret.
- No check for answers that echo the instructions.

**Fix:** keep secrets and authorisation out of prompts (enforce them in code); add a canary or sentinel to the instructions and block answers that contain it or the prompt's delimiters; refuse "repeat the text above"-style requests.

## LLM08 Vector and Embedding Weaknesses

**Look for**
- One vector index shared across tenants or users with no filter on retrieval.
- Access control checked at ingestion but not at query time.
- Embeddings of sensitive text stored without the source's protections.
- Retrieved chunks trusted as instructions (LLM01).

**Fix:** a permission filter on every retrieval (the tenant and user from the session, never from the prompt); separate indexes per tenant where needed; the same retention and encryption as the source data.

## LLM09 Misinformation

**Look for** answers presented as fact in high-stakes areas (financial, medical, legal) with no grounding, no source, and no disclaimer; and promises the product must not make ("guaranteed", "100%").

**Fix:** ground answers in supplied data and say when it is missing; cite sources; add domain disclaimers; block or soften promise language; keep a human in the loop for decisions.

## LLM10 Unbounded Consumption

**Look for** no limit on input length, output tokens, conversation length, requests per user, concurrent requests, or tool-loop steps; memory or caches that grow without bound; no timeout on model calls; retries that multiply cost.

**Fix:** cap input and `max_tokens`; trim history; per-user rate limits and a concurrency cap; timeouts; bounded caches (LRU, TTL); budgets and alerts.

---

## ASI01 Agent Goal Hijack

The agentic form of LLM01. Instructions planted in a document, page, email, ticket or tool result redirect the agent's goal or plan.

**Look for:** agents that read external content and then act; plans that the content can rewrite; no check that each action still serves the user's original request.

**Fix:** keep the user's intent as a fixed record outside the context; check every planned action against it and against an allow-list; tag external content as data; ask for confirmation when the plan changes.

## ASI02 Tool Misuse and Exploitation

**Look for** legitimate tools used in harmful ways: chaining, over-broad arguments (wildcards, mass deletes), ambiguous tool descriptions, tool results trusted blindly, and no rate or scope limit per tool.

**Fix:** narrow tool schemas (enums, bounds, no free-form commands); validate arguments server-side; limit per tool and per session; log every call; dry-run modes for destructive tools.

## ASI03 Identity and Privilege Abuse

**Look for**
- Agents that act under a shared service identity rather than the user's.
- Credentials kept in the context or in memory.
- Privileges inherited across delegation steps (a sub-agent that gets the parent's full token).
- Missing audience or scope checks on tokens agents present.

**Fix:** a distinct identity per agent; delegated, scoped, short-lived tokens bound to the user and the audience (RFC 8707); credentials kept outside the model's context; authorisation re-checked at every hop.

## ASI04 Agentic Supply Chain

**Look for** tools, MCP servers, plugins, prompts or agent cards loaded at runtime from third parties without pinning or verification; and tool descriptions that a server can change after approval ("rug pull").

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
