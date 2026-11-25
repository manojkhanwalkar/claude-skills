# GDPR / UK GDPR and ePrivacy — Checklist for Code and Product

Each item names the article(s) to cite. Security controls for personal data (encryption, masking, log redaction, access control, test data) live in `compliance-check` → `references/pii-privacy.md`; cite them from there rather than repeating them here.

## Contents
- G-MAP Records of processing and the data map (Art. 30)
- G-BASIS Lawful basis and purpose (Art. 5(1)(a)(b), 6, 9, 10)
- G-CONSENT Consent quality (Art. 4(11), 7, 8; EDPB 05/2020)
- G-COOKIE Cookies, SDKs, pixels and device access (ePrivacy Art. 5(3))
- G-DARK Deceptive design in privacy choices (EDPB 03/2022; DSA Art. 25)
- G-NOTICE Transparency (Art. 12–14)
- G-RIGHTS Data subject rights (Art. 15–22)
- G-ADM Automated decisions and profiling (Art. 22)
- G-PBD Privacy by design and by default (Art. 25)
- G-CHILD Children (Art. 8)
- G-DPIA Data protection impact assessment (Art. 35)
- G-PROC Processors and sub-processors (Art. 28)
- G-XFER International transfers (Art. 44–49)
- G-RET Storage limitation (Art. 5(1)(e))
- G-BREACH Breach detection and notification (Art. 33, 34)
- G-AI Personal data in AI systems
- Sources

---

## G-MAP — Records of processing and data map (Art. 30)

- Build or verify the data/tracking map in the report: purpose → data → basis → recipients → transfers → retention. Every new purpose or recipient in a PR updates it (and the design doc).
- Grep starting points: entities and DTOs with personal fields; HTTP clients to third parties; SDK init calls; message producers; analytics events (`track(`, `logEvent(`, `capture(`).

## G-BASIS — Lawful basis and purpose (Art. 5(1)(a)(b), 6, 9, 10)

- Each purpose has one basis: contract, legal obligation, legitimate interests (with a balancing test), consent, vital interests, public task. "Consent" for something the service can't work without is wrong (use contract); "legitimate interests" for intrusive tracking or ads profiling is generally not accepted (CJEU *Meta v Bundeskartellamt*, C‑252/21, 2023).
- **Purpose limitation**: data collected for one purpose (fraud, security, KYC) reused for another (marketing, model training, ads) needs compatibility analysis or a new basis — flag new uses of existing fields in a PR.
- **Special categories (Art. 9)** and criminal-offence data (Art. 10) need an Art. 9(2) condition (often explicit consent) — flag any such field.
- Credit/financial data is not an Art. 9 category but is high-risk (DPIA, AI Act high-risk, FCRA-like rules).

## G-CONSENT — Consent quality (Art. 4(11), 7, 8; EDPB Guidelines 05/2020)

- **Freely given**: not bundled with terms of service; service not conditioned on consent to unrelated processing; "consent or pay" models need a genuine equivalent alternative (EDPB Opinion 08/2024).
- **Specific and granular**: separate toggles per purpose (analytics, personalisation, ads, sharing), none pre-ticked.
- **Informed**: who (controller and recipients named), what, why, before asking.
- **Unambiguous**: an affirmative act — scrolling, continuing to browse or closing the banner is not consent.
- **Demonstrable (Art. 7(1))**: store a consent record — subject id or pseudonymous id, purposes, notice/version, timestamp, method, and the withdrawal.
- **Withdrawable as easily as given (Art. 7(3))**: a persistent link/button to reopen preferences; withdrawal stops processing and the SDKs.
- Check: consent stored server-side or in a CMP; code paths read the purposes before acting (server-side too — an email marketing job must check the marketing consent).

## G-COOKIE — Cookies, SDKs, pixels and device access (ePrivacy Art. 5(3) + GDPR)

- Anything that **stores or reads** on the device — cookies, `localStorage`, IndexedDB, mobile advertising IDs, SDK identifiers, pixels, fingerprinting — needs prior consent unless **strictly necessary** for the service the user asked for (session, load balancing, security, shopping cart, the consent cookie itself, user-interface preferences the user set).
- Analytics: consent needed in most EU states (exceptions: CNIL-style exempted first-party audience measurement configured narrowly; UK DUAA 2025 analytics exemption with opt-out). Session replay, heatmaps, A/B tools, ads, social pixels: consent.
- **Before consent, nothing non-essential loads** — not just "doesn't send". Check `<script>` tags in base templates, tag-manager containers, SDKs initialised in `Application.onCreate` / app start, server-side tagging that still forwards IP and user agent.
- `scan_trackers.py` kinds `tracker`, `third-party-script`, `cookie-write`, `client-storage`, `fingerprinting` are the leads; `consent-check` hits show where gating exists — verify it runs first.
- Cookie attributes for necessary cookies: `Secure`, `HttpOnly` (where JS needn't read), `SameSite`, minimal lifetime.
- Signals: honour the Global Privacy Control where a law requires it (California, Colorado and others for sale/sharing/targeted ads); it's good practice for EU users too.

## G-DARK — Deceptive design in privacy choices (EDPB Guidelines 03/2022; DSA Art. 25; national DPAs' cookie decisions)

- "Reject all" on the first layer with the same prominence (size, colour, clicks) as "Accept all"; no pre-checked boxes; no repeated nagging after refusal; no confusing double negatives; no hiding the settings link; no "legitimate interest" toggles switched on by default for ads vendors.
- Account deletion and privacy settings reachable in no more steps than sign-up.

## G-NOTICE — Transparency (Art. 12–14)

- A privacy notice reachable from every collection point (sign-up, forms, app stores, chatbot) covering controller identity, purposes and bases, recipients, transfers, retention, rights, automated decisions, and source of data not obtained from the person (Art. 14 — e.g. credit bureau data).
- Just-in-time notices for unexpected uses (location, contacts, camera).
- Code check: the notice links exist in the UI, the version shown is recorded with consent.

## G-RIGHTS — Data subject rights (Art. 15–22)

- **Access (15)** and **portability (20)**: export of all personal data held about the person, across every store in the map, machine-readable (JSON/CSV), without other people's data; within one month.
- **Rectification (16)**: personal fields are editable or correctable via support; corrections propagate.
- **Erasure (17)**: an account-deletion/erasure path that deletes or irreversibly anonymises the person's data in every store — DB, caches, search, vector stores and embeddings, files/object storage, queues, analytics, logs per retention, backups by rotation — and notifies processors/recipients (Art. 19). Keep only what a legal obligation requires (financial records), minimised and flagged. Soft-delete flags alone aren't erasure.
- **Restriction (18)** and **objection (21)**: ability to stop a processing purpose for one person (e.g. marketing, profiling) — the code checks the flag. Objection to direct marketing is absolute.
- **Verification**: requests are authenticated or verified proportionately before data is released or deleted.
- Tests: an erasure test that seeds data in every store and asserts it's gone; an export test that asserts every store is included and another user's data is not.

## G-ADM — Automated decisions and profiling (Art. 22; EDPB WP251)

- A decision **based solely on automated processing** (including an LLM's output) that produces legal or similarly significant effects — credit approval or limits, pricing that excludes, account termination, hiring — is allowed only with contract necessity, law or explicit consent, **and** safeguards: meaningful information about the logic, the right to human intervention, to express a view and to contest (CJEU *SCHUFA*, C‑634/21, 2023: a credit score that strongly drives a lender's decision is itself such a decision).
- Check: a human-review path exists and is reachable by the user; explanations of the main factors are generated; decisions and inputs are logged for contestation. Overlaps with AI Act high-risk and FCRA adverse-action notices.

## G-PBD — Privacy by design and by default (Art. 25; EDPB Guidelines 4/2019)

- **By default**: only data necessary for each purpose is processed; optional features, profile visibility, sharing and personalisation off by default; shortest reasonable retention.
- **By design**: minimisation in APIs and forms, pseudonymisation of analytics and logs, purpose-scoped access, separation of identifying data from usage data.
- New field in a PR → ask "which purpose needs it, and is it optional?".

## G-CHILD — Children (Art. 8; UK Age Appropriate Design Code; DSA Art. 28)

- Information society services offered directly to a child relying on consent need parental consent under the national age (13–16). Detect: age gates, date-of-birth fields, content aimed at children.
- High-privacy defaults for minors, no profiling-based ads to minors (DSA Art. 28(2)), no nudge techniques.

## G-DPIA — Impact assessment (Art. 35)

- Required for high-risk processing: large-scale special-category data, systematic monitoring, credit scoring/profiling with significant effects, innovative tech (AI) with personal data, matching datasets, vulnerable subjects. Flag when a PR introduces one of these and the design doc has no DPIA reference.

## G-PROC — Processors and sub-processors (Art. 28)

- Each third party receiving personal data is listed with role (processor or independent controller) and purpose; data sent is minimised; SDKs that make the vendor a controller (ad networks) need consent.
- Code check: outbound calls and SDKs vs the documented processor list; flag unlisted recipients.

## G-XFER — International transfers (Art. 44–49; Schrems II, C‑311/18)

- Data leaving the EEA (and UK) needs adequacy (incl. EU–US Data Privacy Framework for certified US companies), SCCs with a transfer impact assessment, or BCRs. Check cloud regions in IaC/config (`region:`, `eu-west-1` vs `us-east-1`), third-party endpoints, LLM API regions and data-retention settings, support tools.
- Flag a PR that moves EU personal data to a new region or vendor.

## G-RET — Storage limitation (Art. 5(1)(e))

- Each store has an enforced retention (TTL, purge job, lifecycle rule) matching the notice; inactive accounts purged per policy; logs retained only as long as needed. Tests for purge jobs.

## G-BREACH — Breach detection and notification (Art. 33, 34)

- Authority notification within **72 hours** of awareness; affected people without undue delay when high risk. Code-side: detection (alerts on anomalous access/exfiltration), audit logs that let you determine whose data was affected, a contact list in the runbook.

## G-AI — Personal data in AI systems (EDPB Opinion 28/2024; CNIL AI guidance)

- Training or fine-tuning on personal data needs a basis (legitimate interests with a balancing test and opt-out, or consent) and minimisation; document whether a model is anonymous.
- Prompts, RAG stores, embeddings and agent memory are personal data stores: include them in the map, retention and erasure.
- LLM vendor: processor terms, no-training setting, retention, region.
- Outputs about people must be accurate (Art. 5(1)(d)) — hallucinated facts about a person are inaccurate personal data; provide correction paths.

## Sources

- GDPR text: https://eur-lex.europa.eu/eli/reg/2016/679/oj ; ePrivacy Directive 2002/58/EC.
- EDPB Guidelines 05/2020 (consent), 4/2019 (data protection by design and by default), 03/2022 (deceptive design patterns), 2/2023 (technical scope of Art. 5(3) ePrivacy), Opinion 08/2024 (consent or pay), Opinion 28/2024 (AI models); WP251 (automated decision-making).
- CJEU C‑252/21 *Meta Platforms v Bundeskartellamt* (2023); C‑634/21 *SCHUFA* (2023); C‑311/18 *Schrems II* (2020); C‑673/17 *Planet49* (2019).
- ICO guidance; UK Data (Use and Access) Act 2025.
- Legiscope, "GDPR Article 25: Privacy by Design": https://www.legiscope.com/blog/gdpr-article-25-privacy-by-design.html ; Taylor Wessing DPbDD checklist: https://globaldatahub.taylorwessing.com/article/data-protection-by-design-and-default-checklist
- Digital Omnibus status: https://acompli.ie/news/digital-omnibus-gdpr-cookies-status-september-2026/ ; https://usercentrics.com/knowledge-hub/eu-digital-omnibus-package/ ; Council mandate (21 Oct 2026): https://iapp.org/news/a/eu-member-states-finalize-digital-omnibus-negotiating-stance
