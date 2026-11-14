# PII and Privacy — Checklist for Code

Controls that engineers implement for personal data. They map to GDPR (Art. 5 principles, 15–22 rights, 25 data protection by design and by default, 30 records of processing, 32 security of processing, 33/34 breach notification, 44+ transfers), CCPA/CPRA (access, deletion, correction, opt-out of sale/sharing, limit use of sensitive PI, Global Privacy Control), the GLBA Safeguards Rule (16 CFR 314 — encryption of customer information at rest and in transit, MFA, access controls, monitoring and logging, secure development, change management, disposal within two years of last use), NIST SP 800-122 (context-based PII confidentiality impact) and NIST SP 800-53 Rev. 5 privacy controls. HIPAA applies only if health data appears; then flag it and ask.

Each item has an ID (`PII-…`) to cite in findings. Grep hints are leads only.

## Contents
- PII-INV Inventory and classification
- PII-MIN Minimisation and purpose limitation
- PII-ENC Encryption at rest and in transit
- PII-MASK Masking in UIs, APIs and exports
- PII-LOG Logs, metrics, traces and error reports
- PII-ACC Access control and tenant isolation
- PII-RET Retention and disposal
- PII-DSR Data subject rights (access, deletion, correction, portability, opt-out)
- PII-CON Consent and defaults
- PII-3P Third parties, transfers and AI/LLM use
- PII-TEST Test data and non-production
- PII-BRE Breach readiness and audit
- PII-AUTH Credentials and identity
- False positives
- Sources

---

## PII-INV — Inventory and classification

- A data inventory exists (or is produced by this check) listing each PII field, its class, its stores and its recipients. NIST SP 800-122: you cannot protect PII you don't know about. GDPR Art. 30 and CPRA notices depend on it.
- Classes drive controls: **sensitive** (government IDs, DOB+name, financial accounts, credit reports and scores, biometrics, health, precise geolocation, credentials, children's data) needs encryption at rest, masking and access logging; **ordinary** PII (name, email, phone, address, IP, device IDs) needs minimisation, access control and retention.
- Flag a new PII field in a PR whose docs/design doc don't mention it.
- Grep: `ssn|social|taxId|tin\b|dob|birth|passport|licen[cs]e|address|phone|email|firstName|lastName|ip_?address|device_?id|geo|lat(itude)?|lon(gitude)?|credit_?(report|score)|income|salary|gender|race|religion|health|diagnos`

## PII-MIN — Minimisation and purpose limitation (GDPR Art. 5(1)(b)(c), 25; CPRA)

- Collect only fields the feature needs: a form or API that requires full SSN where last four would do, DOB where age-over-18 would do, precise location where region would do.
- Don't return more than the caller needs: entities serialised whole to the API (`return userRepository.findById(...)`), `SELECT *` into responses, GraphQL types exposing every column.
- Don't copy PII into secondary stores (analytics events, search indexes, caches, vector stores, data lakes, LLM prompts) without a purpose; use opaque IDs there.
- Pseudonymise where the purpose allows (GDPR Art. 25, 32(1)(a); NIST IR 8053): tokenise identifiers, use a keyed hash for joins, keep the re-identification key separate.
- Fix: DTOs with explicit allow-listed fields; separate "sensitive" processing paths (CPRA "limit use of sensitive PI").

## PII-ENC — Encryption at rest and in transit (GDPR Art. 32; GLBA 314.4(c)(3); NIST SC-8, SC-28)

- **In transit**: TLS 1.2+ for every hop that carries PII, including service-to-service and to databases and queues; certificate validation never disabled (`verify=False`, trust-all managers).
- **At rest**: sensitive PII encrypted at field level (application-layer or DB column encryption with KMS-managed keys), not only by disk encryption; backups and exports encrypted too; keys outside source and config; key rotation possible (key id stored with ciphertext).
- **Lookups on encrypted fields**: use a separate keyed hash (HMAC) column for equality search; never a plain hash of a low-entropy value (SSN, DOB, phone — brute-forceable in seconds).
- **Crypto choice**: AES-GCM or ChaCha20-Poly1305 with random nonces; no ECB, no static IV, no home-made crypto, no Base64/obfuscation called "encryption".
- Client storage: no sensitive PII in `localStorage`/`sessionStorage`, URLs, query strings or cookies without `Secure; HttpOnly; SameSite`.

## PII-MASK — Masking in UIs, APIs and exports

- Sensitive identifiers shown masked by default (SSN `***-**-1234`, account numbers last 4), unmasked only for a role with a need and with an audit event.
- Masking happens server-side — a full SSN sent to the browser and hidden by CSS/JS is not masked.
- `toString()`, `__repr__`, Lombok `@Data`/`@ToString`, Kotlin/Java records and data classes print every field — exclude sensitive ones (`@ToString.Exclude`, custom `toString`).
- Exports (CSV, PDF, email bodies, push notifications, SMS) follow the same rule; emails carry links behind login, not the data.

## PII-LOG — Logs, metrics, traces and error reports (OWASP Logging Cheat Sheet; GDPR Art. 32; NIST AU-3)

- **Never log**: passwords, tokens, session IDs, keys, connection strings, full government IDs, full financial account/card numbers, credit report contents, health data. Mask, hash (keyed) or drop them; names, emails and phone numbers need a reason and pseudonymisation where possible.
- Hot spots: request/response body logging filters, `log.info("… {}", user)` (prints the whole object), exception messages that echo input (`"invalid SSN " + ssn`), validation errors returned to clients, MDC/trace/span attributes, HTTP access logs with query strings, APM and error trackers (Sentry, Datadog) capturing bodies and local variables, LLM prompt/response logs.
- Prefer a structural control: a masking log encoder / layout, a `Sensitive<T>` wrapper whose `toString` masks, an allow-list of loggable fields; plus a test that captures logs and asserts no unmasked value.
- Log injection: structured (JSON) logs or CR/LF escaping of user data; size limits on logged values.
- Log access is restricted and logs have a retention period — logs are a PII store too.

## PII-ACC — Access control and tenant isolation (GDPR Art. 32; GLBA 314.4(c)(1); NIST AC-3, AC-6)

- Every endpoint, tool, MCP/A2A operation and query that returns PII checks that the caller may see *that person's* data (object-level authorisation, no IDOR). Identity comes from the authenticated principal, not from a request parameter.
- Internal/admin endpoints that read PII are authenticated, authorised by role, and audited.
- Service accounts and DB users have least privilege (no app user with DDL rights; read-only replicas for reporting).
- Bulk access (search, export, list-all) is rate-limited, paginated and audited.

## PII-RET — Retention and disposal (GDPR Art. 5(1)(e); GLBA 314.4(c)(6); CPRA)

- Each PII store has a retention period that code enforces: DynamoDB/Redis TTLs, scheduled purge jobs, S3 lifecycle rules, log retention settings. "Keep forever" needs a documented reason.
- Purges are tested (a test inserts an expired row and asserts it is gone) and cover derived copies (caches, indexes, analytics, backups by rotation).
- GLBA: dispose of customer information no later than two years after last use unless needed for a business or legal reason.

## PII-DSR — Data subject rights (GDPR Art. 15–22; CCPA/CPRA)

- **Access / portability**: a way to export everything held about a person (all stores in the inventory) in a machine-readable form, without other people's data.
- **Deletion / erasure**: a path that deletes or irreversibly anonymises the person's data in every store — primary DB, caches, search, vector stores, queues, files, analytics, third parties (notified) — with legal-hold exceptions (e.g. SOX/financial records that must be retained are kept, minimised and flagged). Soft-delete flags alone don't erase. Test it.
- **Correction**: PII fields are editable and corrections propagate to copies.
- **Opt-out / limit**: honour opt-out of sale/sharing and the Global Privacy Control (`Sec-GPC: 1`) header if the business sells/shares data or does targeted ads; limit use of sensitive PI if used beyond the service.
- Requests are authenticated/verified before data is returned or deleted (an unauthenticated "export my data" is a breach generator).

## PII-CON — Consent and defaults (GDPR Art. 6, 7, 25(2))

- Optional processing (marketing emails, analytics, sharing, model training) is off by default and needs an affirmative action; consent is recorded with timestamp, version of the notice and source, and withdrawal is as easy as giving it.
- Cookies and trackers that aren't strictly necessary load only after consent.

## PII-3P — Third parties, transfers and AI/LLM use (GDPR Art. 28, 44+; CPRA service-provider rules)

- List every third party that receives PII (email/SMS providers, analytics, error trackers, LLM APIs, credit bureaus, KYC vendors) and what fields; flag any that receive more than they need.
- **LLMs**: redact or tokenise PII before it goes into a prompt, a tool result, a vector store or agent memory; don't log prompts/responses with PII; check the provider's data-retention and no-training settings; guard against the model echoing another user's data (see `owasp-llm-top10` LLM02).
- Cross-border transfers (e.g. EU data to US regions) need a basis — flag region configuration that moves data unexpectedly.

## PII-TEST — Test data and non-production

- No real personal data in tests, fixtures, seed data, staging dumps or screenshots; use synthetic data (Faker, generators) and placeholder IDs (SSN `123-45-6789` and the 9xx range are never issued). Real-looking SSNs outside the placeholder set in fixtures are a finding until shown synthetic.
- Production snapshots used in lower environments are masked first.

## PII-BRE — Breach readiness and audit (GDPR Art. 33/34 — 72 hours; GLBA 314.4(j) — FTC notice within 30 days for ≥500 consumers; state laws)

- Access to sensitive PII is audit-logged (who, whose record, when, why/endpoint) so a breach's scope can be determined.
- Alerts exist for anomalous access (bulk reads, many failed authorisations).
- The design doc names where PII lives and who to call — the inventory is the incident-response map.

## PII-AUTH — Credentials and identity (GLBA 314.4(c)(5) MFA; NIST IA)

- Passwords hashed with Argon2id / bcrypt / scrypt / PBKDF2 (per OWASP Password Storage Cheat Sheet); MFA for staff and for any access to customer information systems; KYC documents (ID scans, selfies) treated as sensitive PII with strict retention.

## False positives

- Placeholder SSNs (`123-45-6789`, `078-05-1120`, 9xx area numbers) and Faker data in tests.
- `address` meaning a network or memory address; `name` meaning a field/file name.
- Data about businesses rather than individuals (though a sole trader's data is personal).

## Sources

- NIST SP 800-122, *Guide to Protecting the Confidentiality of PII*: https://csrc.nist.gov/pubs/sp/800/122/final
- NIST SP 800-53 Rev. 5 (privacy and security controls) and NIST IR 8053 (de-identification).
- GDPR (Regulation (EU) 2016/679), Articles 5, 15–22, 25, 30, 32–34; EDPB Guidelines 4/2019 on Data Protection by Design and by Default.
- California CCPA as amended by CPRA; CPPA regulations (Cal. Code Regs. tit. 11, §7000 et seq.).
- FTC GLBA Safeguards Rule, 16 CFR Part 314 (as amended 2021/2023).
- OWASP Logging Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html ; OWASP User Privacy Protection and Password Storage cheat sheets.
- Transcend, "Engineering implications from the CPRA": https://transcend.io/blog/engineering-implications-cpra
- Taylor Wessing, "Data protection by design and default checklist": https://globaldatahub.taylorwessing.com/article/data-protection-by-design-and-default-checklist
