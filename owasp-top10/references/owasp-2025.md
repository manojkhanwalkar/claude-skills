# OWASP Top 10:2025 — Audit Checklist

Per category: what to look for, grep starting points, and common false positives. Grep patterns are leads only — confirm by reading the code and tracing data flow.

The hints cover Java, Python and JavaScript first, then Go, Ruby, PHP and C# where a pattern differs. Translate them to the stack you found in Phase 1; for other languages, look for the same sinks (query building, process execution, deserialization, file paths, outbound URLs).

## Contents
- A01 Broken Access Control
- A02 Security Misconfiguration
- A03 Software Supply Chain Failures
- A04 Cryptographic Failures
- A05 Injection
- A06 Insecure Design
- A07 Authentication Failures
- A08 Software or Data Integrity Failures
- A09 Security Logging and Alerting Failures
- A10 Mishandling of Exceptional Conditions
- 2021 → 2025 mapping

---

## A01 Broken Access Control (includes SSRF)

**Look for**
- Endpoints/handlers with no authorization check, or checks only in the UI/client.
- IDOR: object IDs from the request used to load data without verifying ownership/tenant.
- Missing function-level checks (admin operations reachable by regular users).
- Path traversal: user input joined into file paths without canonicalization + base-dir check.
- CORS `*` with credentials; permissive origin reflection.
- JWT/session claims trusted without verification; role taken from request body.
- SSRF: server fetches a user-supplied URL/host without allowlist (watch for redirects, `file://`, internal IPs, cloud metadata `169.254.169.254`).
- Default-allow instead of default-deny.
- CSRF: state-changing requests authenticated by cookies without a CSRF token or `SameSite` protection.
- Mass assignment / over-posting: request bodies bound directly to entities or models, so callers can set `role`, `isAdmin`, `ownerId` or `price`.
- Open redirects: redirect targets taken from request parameters without an allowlist.

**Grep hints**
`@RequestMapping|@GetMapping|@PostMapping|@Path|app\.(get|post)|router\.|@app\.route` ·
`permitAll|@PreAuthorize|@Secured|isAdmin|hasRole` ·
`new File\(|Paths\.get|path\.join|open\(.*req|\.\./` ·
`Access-Control-Allow-Origin|allowedOrigins` ·
`new URL\(|HttpClient|RestTemplate|fetch\(|requests\.get|urlopen` ·
`csrf\(\)\.disable|csrf_exempt|protect_from_forgery|skip_forgery_protection` ·
`redirect\(.*(req|request|params)|sendRedirect\(|res\.redirect\(`

Other stacks: Go `http.HandleFunc|mux\.Handle|r\.(GET|POST)` · Ruby `skip_before_action :authenticate|params\.permit!` · PHP `\$_(GET|POST|REQUEST)\[` reaching `include|file_get_contents` · C# `\[AllowAnonymous\]|\[Authorize`

**False positives**: internal-only services behind an authenticating gateway (note as Plausible, state assumption); paths built from constants.

## A02 Security Misconfiguration

**Look for**
- Debug mode, verbose error pages, stack traces returned to clients.
- Default/sample credentials, accounts, or config left enabled.
- Insecure TLS settings: trust-all `TrustManager`, hostname verification disabled, `verify=False`, `rejectUnauthorized: false`, TLS < 1.2 enabled.
- Missing security headers (CSP, HSTS, X-Content-Type-Options) on web apps.
- XML parsers with external entities enabled (XXE) — DTD/external entity processing not disabled.
- Overly broad file permissions, world-readable key files, containers running as root.
- Unnecessary features/ports/endpoints enabled (actuator, admin consoles, directory listing); admin interfaces bound to all interfaces.
- Session cookies missing `Secure`, `HttpOnly` or `SameSite`.
- No request or body size limits (uploads, JSON bodies, multipart), allowing memory exhaustion.
- GraphQL introspection or the playground enabled in production; no query depth or complexity limits.

**Grep hints**
`debug\s*=\s*true|DEBUG = True|printStackTrace|setDebug` ·
`X509TrustManager|checkServerTrusted|HostnameVerifier|ALLOW_ALL|verify=False|rejectUnauthorized|InsecureSkipVerify` ·
`DocumentBuilderFactory|SAXParserFactory|XMLInputFactory|lxml|etree` (check feature flags) ·
`management\.endpoints|actuator|adminConnectors|bindHost|0\.0\.0\.0` · `USER root|chmod 777` ·
`HttpOnly|SameSite|secure:\s*false|SESSION_COOKIE_SECURE` · `introspection|playground|maxBodySize|client_max_body_size|MaxRequestBodySize`

Other stacks: Go `InsecureSkipVerify|http\.ListenAndServe\(":` · Ruby `config\.force_ssl\s*=\s*false|consider_all_requests_local` · PHP `display_errors|expose_php` · C# `UseDeveloperExceptionPage|ServerCertificateCustomValidationCallback`

**False positives**: test-only TLS bypass in test sources; debug flags read from env that default to off.

## A03 Software Supply Chain Failures

**Look for**
- Dependencies with known CVEs; badly outdated major versions; abandoned libraries.
- Unpinned versions (`latest`, ranges, `+`, `SNAPSHOT` in release builds), missing lockfiles.
- Dependencies pulled from untrusted/HTTP repositories; custom repos without integrity checks.
- Build scripts that `curl | sh` or download artifacts without checksum/signature verification.
- CI workflows: unpinned third-party actions (`@main`/`@v1` rather than SHA), secrets exposed to PR builds from forks, `pull_request_target` misuse.
- Docker base images unpinned (`:latest`) or from unknown publishers.

**Grep hints**
manifest files · `<repository>|repositories \{|http://` · `curl .*\| *(ba)?sh|wget ` · `.github/workflows/*.yml: uses:` · `FROM .*:latest`

**Before calling a dependency unused:** check test sources; runtime, reflective, `ServiceLoader` and plugin use; and transitive needs (for example a crypto provider or codec that another library loads at runtime). Use the build tool's analysis (`mvn dependency:analyze`, `depcheck`, `go mod why`, `cargo udeps`), and confirm by building and running the tests after removal. The right fix is often to narrow the scope (test, dev or optional) rather than remove the dependency.

**Actions:** run an available scanner (see `build-tools.md`). Otherwise list notable dependency versions and flag any you know have serious CVEs, as Plausible with the version.

## A04 Cryptographic Failures

**Look for**
- Weak/broken algorithms: MD5, SHA-1 for signatures/passwords, DES/3DES, RC4, RSA < 2048, ECB mode.
- Unauthenticated encryption (CBC/CTR without MAC) where integrity matters; prefer AEAD (GCM, ChaCha20-Poly1305).
- IV/nonce reuse, static or zero IVs, GCM nonce reuse (catastrophic).
- Non-CSPRNG for security values (`java.util.Random`, `Math.random`, Python `random`).
- Hardcoded keys, passwords, salts; keys in source, config committed to repo, or logs.
- Secrets in git history, not just HEAD: `git log --all --oneline -- '*.jks' '*.p12' '*.pem' '*.key' '.env'`, `git log -p -S'PRIVATE KEY'`, or `gitleaks` / `trufflehog` if installed. Deleting a file doesn't un-leak it.
- Secrets or keys packaged into build artifacts (jar/war resources, Docker image layers, frontend bundles).
- Password hashing without a slow KDF (bcrypt, scrypt, Argon2, PBKDF2 with high iterations).
- Non-constant-time comparison of MACs/tokens (`equals`, `==`) — timing leaks.
- RSA with PKCS#1 v1.5 encryption padding (prefer OAEP); missing signature verification.
- Sensitive data stored/transmitted in cleartext; keys not zeroed/rotated; key material in `String`.
- Custom crypto protocols — check for replay protection, key separation, and downgrade risks.

**Grep hints**
`Cipher\.getInstance|MessageDigest|Mac\.getInstance|KeyGenerator|KeyPairGenerator|Signature\.getInstance` ·
`MD5|SHA1|SHA-1|DES|RC4|ECB|NoPadding|PKCS1Padding` ·
`new Random\(|Math\.random|import random` ·
`IvParameterSpec|GCMParameterSpec|new byte\[(12|16)\]` ·
`password\s*=\s*"|secret\s*=\s*"|BEGIN (RSA )?PRIVATE KEY|apiKey` ·
`Arrays\.equals|\.equals\(.*(mac|hmac|tag|signature)` (vs `MessageDigest.isEqual`)

Other stacks: Go `crypto/md5|crypto/sha1|crypto/des|math/rand|bytes\.Equal\(.*(mac|sig)` (vs `hmac.Equal`) · Ruby `Digest::MD5|OpenSSL::Cipher.*ecb|rand\(` · PHP `md5\(|sha1\(|mt_rand|rand\(|openssl_encrypt\(.*ECB` · C# `MD5\.Create|SHA1\.Create|DESCryptoServiceProvider|new Random\(|CipherMode\.ECB`

**False positives**: MD5/SHA-1 used for non-security checksums (cache keys, ETags); `Random` for non-security jitter.

## A05 Injection (includes XSS)

**Look for**
- SQL/NoSQL/LDAP/XPath built via string concatenation or formatting with untrusted input.
- OS command execution with untrusted input; `shell=True`; `Runtime.exec` with a single concatenated string.
- Template/expression injection (SpEL, OGNL, Jinja `render_template_string`, EL).
- XSS: untrusted data rendered into HTML/JS without context-aware encoding; `innerHTML`, `dangerouslySetInnerHTML`, `|safe`, `th:utext`.
- Log injection (CRLF in log messages), header injection, CSV/formula injection.
- `eval`, dynamic code loading from input.
- ReDoS: user input matched against regexes with nested quantifiers, or user-supplied regexes.
- Prototype pollution (JavaScript): deep `merge` / `Object.assign` / `_.set` with request data.
- Prompt injection: untrusted text fed to an LLM whose output reaches tools, shell, SQL or HTML without validation.

**Grep hints**
`executeQuery|createQuery|createNativeQuery|Statement\b|\+ *".*(SELECT|WHERE|INSERT)|f"SELECT|format\(.*SELECT` ·
`Runtime\.getRuntime\(\)\.exec|ProcessBuilder|subprocess|os\.system|child_process|exec\(` ·
`eval\(|ScriptEngine|SpelExpressionParser|render_template_string` ·
`innerHTML|dangerouslySetInnerHTML|\|safe|th:utext|v-html` ·
`new RegExp\(.*(req|params|input)|Pattern\.compile\(.*(request|param)` · `merge\(.*req\.body|Object\.assign\(.*req\.body|_\.set\(`

Other stacks: Go `db\.(Query|Exec)\(fmt\.Sprintf|exec\.Command\("sh",\s*"-c"|template\.HTML\(` · Ruby `find_by_sql|where\(".*#\{|system\(|%x\(|html_safe|raw\(` · PHP `mysqli_query\(.*\$_|->query\(.*\$|shell_exec|passthru|system\(|echo \$_` · C# `SqlCommand\(.*\+|FromSqlRaw\(.*\+|Process\.Start\(|Html\.Raw\(`

**False positives**: parameterized queries / prepared statements with `?` placeholders; ORM criteria APIs; framework auto-escaping templates.

## A06 Insecure Design

Design flaws that no amount of correct implementation fixes. Judge against the system's purpose.

**Look for**
- Missing threat-model-level controls: no rate limiting/anti-automation on sensitive flows (login, OTP, payments), no replay protection for messages/transactions, no idempotency.
- Trust placed in the client for security decisions (prices, roles, amounts, validation).
- Business-logic abuse: negative quantities, race conditions on balances (check-then-act without locking/transactions), skipping workflow steps.
- Missing separation of duties/tenants; shared keys across tenants or environments.
- Secrets or keys exchanged in ways that defeat the protocol's goal (e.g. both encryption and decryption keys on an untrusted endpoint).
- No limits on resource consumption (unbounded uploads, payload sizes, in-memory caches or session stores that grow forever).
- Unrestricted file upload: no type or size checks, files stored under the web root or under user-controlled names.

**Approach**: Compare the system summary's assets/trust boundaries with the controls actually present. Name the missing control and the abuse case.

## A07 Authentication Failures

**Look for**
- Missing authentication on endpoints/channels that need it; mutual TLS expected but not enforced.
- Weak password policy; no brute-force protection/lockout/backoff; credential stuffing exposure.
- Session IDs in URLs, not rotated after login, no expiry/idle timeout, not invalidated on logout.
- JWT: `alg: none` accepted, weak HMAC secrets, no expiry/audience/issuer checks, signature not verified.
- Hardcoded or default credentials; credentials in logs.
- Insecure password reset / "remember me" token design; predictable tokens.

**Grep hints**
`login|authenticate|password|session|JWT|Jwts\.|jsonwebtoken|PyJWT|setMaxInactiveInterval|remember` ·
`parseClaimsJwt|decode\(.*verify\s*=\s*False|algorithms=\[`

## A08 Software or Data Integrity Failures

**Look for**
- Insecure deserialization of untrusted data: Java `ObjectInputStream`, `XMLDecoder`, Jackson default typing / `@JsonTypeInfo(use = CLASS)`, Python `pickle`/`yaml.load`, .NET `BinaryFormatter`.
- Data/messages/updates accepted without integrity verification (no MAC/signature) or where the signature isn't checked before use.
- Auto-update or plugin loading without signature verification.
- Integrity checks that can be bypassed (verify after use, compare with non-constant-time, accept missing signature).
- CI/CD pipelines where untrusted input can modify build artifacts.

**Grep hints**
`ObjectInputStream|readObject|XMLDecoder|enableDefaultTyping|activateDefaultTyping|JsonTypeInfo|pickle\.loads|yaml\.load\(|BinaryFormatter|Marshal\.load` ·
`verify\(|Signature|Mac\.doFinal`

Other stacks: Go `gob\.NewDecoder` on untrusted input · Ruby `Marshal\.load|YAML\.load\(|Oj\.load` · PHP `unserialize\(` · C# `BinaryFormatter|TypeNameHandling\.(All|Auto|Objects)|NetDataContractSerializer|LosFormatter`

## A09 Security Logging and Alerting Failures

**Look for**
- Security-relevant events not logged: auth success/failure, access denied, decryption/MAC failures, replay detections, admin actions.
- Sensitive data in logs: passwords, keys, tokens, full card numbers (PAN), PII.
- Logs that can be forged (unescaped user input → CRLF injection).
- Errors swallowed silently so attacks leave no trace; no alerting hook for repeated failures.
- `System.out.println`/`print` used instead of a logger in server code (no levels, no shipping).

**Grep hints**
`log\.(info|debug|warn|error)|logger\.|System\.out\.print|console\.log|print\(` combined with `key|secret|password|token|pan|card|cvv`

## A10 Mishandling of Exceptional Conditions

New in 2025: failing open, leaking info on error, or leaving inconsistent state.

**Look for**
- Fail-open logic: exception in an auth/validation/crypto check results in access granted or processing continuing.
- Empty or overly broad catch blocks (`catch (Exception e) {}`) around security checks.
- Error responses that leak stack traces, internal paths, SQL, or crypto details (padding-oracle style distinguishable errors).
- Resources not released on error (streams, locks, connections) → DoS; partial transactions not rolled back.
- Unchecked null/return values; integer overflow on lengths/sizes; unbounded recursion or input sizes.
- Distinct error messages that enable enumeration (user exists vs. wrong password; bad MAC vs. bad padding).

**Grep hints**
`catch\s*\(\s*(Exception|Throwable|RuntimeException)|except:|except Exception|catch \{` ·
`e\.getMessage\(\)|printStackTrace|traceback` in response paths ·
`finally|try-with-resources|with open` (check absence where resources are opened)

---

## 2021 → 2025 mapping (for reference)

| 2025 | Closest 2021 |
|---|---|
| A01 Broken Access Control | A01 Broken Access Control + A10 SSRF |
| A02 Security Misconfiguration | A05 Security Misconfiguration |
| A03 Software Supply Chain Failures | A06 Vulnerable and Outdated Components (broadened) |
| A04 Cryptographic Failures | A02 Cryptographic Failures |
| A05 Injection | A03 Injection |
| A06 Insecure Design | A04 Insecure Design |
| A07 Authentication Failures | A07 Identification and Authentication Failures |
| A08 Software or Data Integrity Failures | A08 Software and Data Integrity Failures |
| A09 Security Logging and Alerting Failures | A09 Security Logging and Monitoring Failures |
| A10 Mishandling of Exceptional Conditions | (new) |
