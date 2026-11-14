# PCI DSS v4.0.1 — Checklist for Code and Pipelines

The requirements below are the ones application code, configuration and CI/CD can satisfy or break. Requirement numbers are PCI DSS v4.0.1 (June 2024; a limited revision of v4.0 with no new or deleted requirements). Every future-dated v4.0 requirement has been mandatory since **31 March 2025**. Wording here is a paraphrase — quote the standard from the PCI SSC document library when a finding is disputed.

Grep hints are leads only: read the code and trace the data.

## Contents
- Scope first (12.5.2, SAQ type)
- 3 Protect stored account data
- 4 Protect data in transit
- 6 Secure software development and change control
- 6.4.3 / 11.6.1 Payment page scripts
- 7 & 8 Access control and authentication
- 10 Audit logging
- 12.8 Third-party service providers
- Common false positives
- Sources

---

## Scope first

- **What is account data?** Cardholder data (CHD) = PAN, plus name, expiry and service code *when stored with the PAN*. Sensitive authentication data (SAD) = full track/chip data, CVV/CVC/CID (card verification code), PIN and PIN block. PCI applies to every system component that **stores, processes or transmits** CHD/SAD, and to anything connected to or able to affect its security.
- **12.5.2 / 12.5.2.1**: scope must be documented and confirmed (annually; every 6 months for service providers), including every data flow and location of account data. In code: the data inventory from Phase 1 *is* the scope evidence. Flag any flow of PAN that the project's docs don't mention.
- **Reduce scope before you protect it.** The best finding fix is often "stop touching PAN": use the processor's hosted fields / iframe / redirect (Stripe Elements or Checkout, Braintree Hosted Fields, Adyen Drop-in, Recurly.js) and keep only the processor token, brand, last four and expiry. Then the merchant typically files **SAQ A** (iframe/redirect) or **SAQ A-EP** (your page posts card data via JS you control).
- **SAQ A since v4.0.1**: 6.4.3 and 11.6.1 were removed from SAQ A, but the merchant must confirm its site is *not susceptible to attacks from scripts that could affect the e-commerce system* — in practice, the same script controls (see below). SAQ A-EP and SAQ D must implement 6.4.3 and 11.6.1 in full.
- Grep: `card_?number|cardNumber|pan\b|primary_?account|cc_?num|creditCard|expiry|exp_?month|cvv|cvc|security_?code|track|pin_?block|stripe|braintree|adyen|recurly|checkout|payment_?method|tokeni[sz]`

## 3 — Protect stored account data

| Req | Check in code | Typical fix |
|---|---|---|
| **3.2.1** | Account data is kept only as long as a documented need; a purge exists for each store (DB, files, queues, caches, logs, backups). | Retention constant + scheduled purge job with a test; TTL on caches/queues. |
| **3.3.1 / 3.3.1.1–3** | **No SAD after authorization, even encrypted**: no CVV column, field, cache entry, log line, queue message or "retry payload" holding CVV, track or PIN. CVV may exist in memory only for the one authorization call. | Remove the field; don't put it on any persisted DTO; pass straight to the processor; scrub request bodies from logs and error reporters. |
| **3.3.2** | SAD kept *before* authorization (e.g. card-on-file setup in progress) is encrypted with strong cryptography. | Prefer never holding it: processor tokenises client-side. |
| **3.4.1** | **PAN masked when displayed**: at most the BIN (first 6, or first 8 for 8-digit BINs) and last 4 shown, and only roles with a documented need see more. Check UI, APIs, emails, PDFs, admin consoles, CSV exports, `toString()`. | One `maskPan()` / `Pan` type used by every rendering; default to last 4 only. |
| **3.4.2** | Remote-access technologies can't copy or relocate PAN (no "export cards" admin feature, no clipboard/CSV download of full PAN) without explicit authorisation. | Remove or gate export; audit it. |
| **3.5.1** | **PAN unreadable wherever stored** — one of: one-way **keyed** hash of the whole PAN (3.5.1.1: unkeyed hashes such as `sha256(pan)` are not compliant; the PAN space is small enough to brute-force), truncation, index tokens, or strong cryptography with managed keys. Hashed and truncated versions of the same PAN must not both be stored where they can be correlated. | Store the processor token instead; if you must store PAN, encrypt with a KMS/HSM-held key (envelope encryption) or HMAC with a secret key for lookups. |
| **3.5.1.2** | Disk/volume or transparent DB encryption **alone** is not enough for PAN on non-removable media (it decrypts for every reader). | Field-level encryption on top. |
| **3.6 / 3.7** | Key management: keys not in source, config files or images; data-encrypting keys separate from key-encrypting keys; rotation (cryptoperiod) supported; key access limited to the fewest custodians; key generation from a CSPRNG; a way to retire/replace keys. | KMS (AWS KMS, GCP KMS, Vault Transit); key id stored with ciphertext so rotation works; no `new SecretKeySpec("hardcoded"…)`. |

Grep: `sha(1|256|512)\(|MessageDigest|hashlib|digest\(` near PAN · `@Column.*(card|pan)` · `SecretKeySpec|AES/ECB|DES|RC4|Base64` near card fields (Base64 is not encryption) · `cvv|cvc|cid|securityCode` on entities, DTOs, logs.

## 4 — Protect data in transit

- **4.2.1**: PAN over open, public networks only with strong cryptography — TLS 1.2+ with strong suites; certificates valid, not expired or revoked; certificate validation never disabled. Check HTTP clients (`TrustAllCerts`, `verify=False`, `InsecureSkipVerify`, `rejectUnauthorized: false`, `NoopHostnameVerifier`), `http://` URLs to payment endpoints, webhook receivers.
- **4.2.1.1**: an inventory of trusted keys and certificates used to protect PAN in transit.
- **4.2.2**: PAN never sent by end-user messaging (email, SMS, chat) — including support chatbots and alert emails; mask before sending.
- Also internal hops: PAN between your own services over plaintext HTTP, Kafka without TLS, or in message bodies that are logged.

## 6 — Secure software development and change control

| Req | Check | Fix |
|---|---|---|
| **6.2.1** | Software developed per a documented secure SDLC. | The project's CLAUDE.md / CONTRIBUTING rules + CI. |
| **6.2.2** | Developers trained at least annually on secure coding for their languages. | Out of scope for code — list under "not checked". |
| **6.2.3 / 6.2.3.1** | Every change to bespoke and custom software (including APIs) reviewed **before release** by someone other than the author, for security and coding vulnerabilities; manual reviews approved by management. | Required PR review (author ≠ approver), branch protection, `pr-review`. |
| **6.2.4** | Code prevents common attacks: injection, attacks on data structures, crypto misuse, business-logic abuse (e.g. card testing, replaying a payment), access-control bypass. | `security-review` / `owasp-top10`; rate limits and velocity checks on payment endpoints. |
| **6.3.1 / 6.3.3** | Vulnerabilities identified and ranked; critical/high patches applied within one month. | Dependabot / dependency review, CodeQL. |
| **6.3.2** | Inventory of bespoke software and third-party components (an SBOM). | SBOM generation in CI (CycloneDX / SPDX). |
| **6.4.1 / 6.4.2** | Public-facing web apps protected by an automated solution that detects and prevents web attacks (WAF), actively running and logging. | Infrastructure; note if absent from IaC. |
| **6.5.1 / 6.5.2** | Changes to production follow change control: reason, security impact, approval, testing, rollback plan; PCI requirements re-confirmed after significant changes. | PR template sections; release workflow with environment approval. |
| **6.5.3 / 6.5.4** | Pre-production separated from production; separation of duties between those who develop and those who deploy to production. | Separate accounts/projects/credentials; deploy only by pipeline. |
| **6.5.5** | **Live PANs not used in pre-production** (tests, fixtures, seed data, staging) — except in a pre-prod environment itself in PCI scope. | Use network test PANs; scanner `pan` hits in tests are High. |
| **6.5.6** | Test data and test accounts removed before production. | No default/test users seeded in prod profiles; `@Profile("!prod")` on seeders. |

## 6.4.3 / 11.6.1 — Payment page scripts

Applies to any page that collects card data **or that embeds the processor's iframe** (the parent page can be attacked to replace the iframe).

- **6.4.3**: every script on the payment page is (a) authorised, (b) has its integrity assured, and (c) is inventoried with a written business or technical justification. Check templates for `<script src=...>` without `integrity=` (SRI) on third-party origins, tag managers, analytics, chat widgets, A/B tools, `eval`/dynamic script injection.
- **11.6.1**: a change- and tamper-detection mechanism alerts on unauthorised changes to the payment page's HTTP headers and script content, at least weekly (or per the targeted risk analysis). Check for a **Content-Security-Policy** with `script-src` allow-list (+ `report-to` / `report-uri`), `frame-src` limited to the processor, and a monitoring job or vendor.
- Fixes: CSP with nonces or hashes, SRI on static third-party scripts, remove non-essential scripts from checkout, script inventory file in the repo with justifications, CSP violation reporting wired to alerts.

## 7 & 8 — Access control and authentication

- **7.2.1–7.2.6**: least privilege and deny by default for access to account data; application and system accounts get only what they need; **7.2.6** user queries of stored cardholder data are restricted to the least privileges. Check DB grants, IAM policies in IaC, admin endpoints, and that one customer can never read another's payment methods (IDOR).
- **8.2.1 / 8.2.2**: unique IDs; shared or generic accounts only by exception.
- **8.2.6 / 8.2.8**: inactive accounts disabled within 90 days; sessions re-authenticate after **15 minutes** idle (for access to the CDE / admin consoles).
- **8.3.1, 8.4.2, 8.4.3, 8.5.1**: MFA for all access into the CDE and for all remote access; MFA not replayable or bypassable.
- **8.3.4**: lockout after at most 10 failed attempts, for at least 30 minutes or until identity is confirmed.
- **8.3.6**: passwords at least **12 characters** (8 if the system can't) with letters and numbers; **8.3.7** not one of the last 4; **8.3.2** stored and transmitted unreadable (salted, slow hash — bcrypt, scrypt, Argon2, PBKDF2).
- **8.6.1–8.6.3**: system and application accounts that can log in interactively are controlled; **their passwords are not hard-coded in scripts, config files or source**; rotated per risk analysis. Grep: `password\s*[=:]`, `jdbc:.*password=`, `.env` committed, `docker-compose` secrets.

## 10 — Audit logging

- **10.2.1**: audit logs record: **10.2.1.1** all individual user access to cardholder data; **.2** all actions by administrative accounts; **.3** all access to audit logs; **.4** invalid logical access attempts; **.5** changes to identification and authentication credentials (create, elevate privileges, change/delete accounts); **.6** initialisation, stopping or pausing of audit logs; **.7** creation and deletion of system-level objects.
- **10.2.2**: each entry has user ID, event type, date and time, success or failure, origin, and the identity or name of the affected data, component or resource.
- **10.3.1–10.3.4**: logs protected from modification; read access limited; promptly backed up to a central server; file-integrity monitoring or change detection on logs.
- **10.4.1.1**: automated log review. **10.5.1**: retain audit logs **12 months**, the last **3 months** immediately available. **10.6**: time synchronised (NTP; UTC timestamps).
- **10.7.2**: failures of critical security controls (including audit logging) detected, alerted and responded to.
- Logs must not contain PAN (unmasked) or SAD — check request/response body logging, exception messages, MDC/trace attributes, HTTP access logs with query strings.

## 12.8 — Third-party service providers

- Every payment processor, tokenisation vendor, hosting or support tool that touches account data or can affect its security is listed, with a written agreement and their PCI status (AOC) tracked. In code: list each provider SDK found, and flag providers that receive PAN or SAD (including error trackers, APM, log shippers and LLM APIs that might receive request bodies).

## Common false positives

- 16-digit IDs that fail Luhn, or pass Luhn but have no card-brand prefix; order numbers, timestamps, phone numbers.
- Network test PANs (`4111 1111 1111 1111`, `4242 4242 4242 4242`, `5555 5555 5555 4444`, …) in tests — fine (6.5.5 forbids *live* PANs).
- Processor tokens (`pm_…`, `tok_…`, `card_…`), last four digits, brand, expiry stored without PAN.
- The word `pin` meaning "pinned", `track` meaning analytics tracking, `cid` meaning correlation/client ID — read the context.

## Sources

- PCI SSC, *PCI DSS v4.0.1* (June 2024) and *Summary of Changes v4.0 → v4.0.1*: https://www.pcisecuritystandards.org/document_library/
- PCI SSC, *Guidance for PCI DSS Requirements 6.4.3 and 11.6.1* (2025) and the SAQ A eligibility FAQ.
- Qualys, "PCI DSS 4.0.1: Application Requirements You're Being Assessed On in 2026": https://blog.qualys.com/product-tech/2026/08/27/pci-dss-4-0-1-application-requirements-youre-being-assessed-on-in-2026
- SecurityMetrics, "A Guide to New Requirements in PCI DSS 4.0.1": https://www.securitymetrics.com/blog/a-guide-to-new-requirements-in-pci-dss-4-0-1
- Report URI, "PCI DSS 4.0.1 and Requirements 6.4.3 and 11.6.1": https://blog.report-uri.com/pci-dss-4-0-1-and-requirements-6-4-3-and-11-6-1-what-changed-for-payment-page-scripts/
- Barr Advisory / Cloud Security Alliance, "PCI DSS 6.4.3 and 11.6.1: A Deep Dive into Payment Page Security": https://www.barradvisory.com/resource/pci-payment-page-security/
- Entrust, "Protecting Stored Cardholder Data: A Guide to PCI DSS v4.0.1 Compliance" (Requirement 3).
