# SOX — Checklist for Code, Repositories and Pipelines

Sarbanes-Oxley §404 requires management (and, for accelerated filers, the external auditor under PCAOB AS 2201) to assess internal control over financial reporting (ICFR); §302 has officers certify it. For software this means two things auditors test:

1. **IT general controls (ITGCs)** over every system that matters to financial reporting — the four domains in COSO/COBIT-based audits: **access to programs and data**, **program change**, **program development**, **computer operations**. In a modern repo most ITGC evidence comes from GitHub and CI/CD settings.
2. **Application controls** in the code — automated controls whose correct operation the auditor relies on: calculations, validations, interfaces, reports, audit trails.

SOX scope is a business decision (public company or pre-IPO, financially significant system). If unknown, check as good practice and lower severities one step (SKILL.md, Phase 1). Each item has an ID to cite.

## Contents
- SOX-CM Change management (program change)
- SOX-SOD Segregation of duties
- SOX-AC Access to programs and data
- SOX-OPS Computer operations (jobs, backups, interfaces)
- SOX-AT Audit trail of financial data
- SOX-CALC Accuracy of financial calculations
- SOX-MC Maker-checker and authorisation
- SOX-INT Interfaces and completeness
- SOX-RPT Reports and end-user computing
- SOX-RET Record retention
- SOX-EVD Evidence
- Sources

---

## SOX-CM — Change management

Auditors pick a sample of production changes and ask: was each one requested, tested, approved by someone other than the developer, and deployed through the controlled path? Can any change reach production without that?

- **CM1 — every change goes through a PR** to the protected production branch; no direct pushes, including by admins (`enforce_admins`), no force pushes or deletions. Check: `gh api repos/{owner}/{repo}/branches/<default branch>/protection` and the rules that apply to it (`gh api repos/{owner}/{repo}/rules/branches/<default branch>`), which include org- and repo-level rulesets.
- **CM2 — independent approval**: at least one approving review by someone other than the author; stale approvals dismissed on new commits; last-push approval required (so the approver saw the final code); CODEOWNERS review for financial modules.
- **CM3 — tested before deploy**: required status checks (build, tests, coverage) must pass; branch must be up to date.
- **CM4 — deployment only by pipeline** from the protected branch, with an environment protection rule (required reviewers, `main`-only deployment branches) for production; no manual `kubectl apply`, console edits, or SSH changes. Deploy workflows use OIDC, not long-lived cloud keys.
- **CM5 — traceability**: PR ↔ ticket/requirement ↔ commit ↔ build ↔ deployed artifact (immutable image digest or signed release). A PR template that records reason, risk, testing and rollback.
- **CM6 — database and configuration changes are changes too**: schema migrations (Flyway, Liquibase, Alembic) versioned in the repo and applied by the pipeline; no ad-hoc SQL in production; feature flags and config that change financial behaviour (prices, fees, interest rules, tax) are version-controlled and approved, or their admin UI is audited and permissioned.
- **CM7 — emergency changes**: a documented break-glass path that still produces a retrospective review and approval.
- Private repos on GitHub Free cannot enforce branch protection: say so, and name the compensating control (rule that every PR goes through `pr-review` by a separate agent, merged only on green CI, plus periodic review of `git log --first-parent main` for commits without a PR).

## SOX-SOD — Segregation of duties

- **SOD1** — the same person can't both develop and approve, or both approve and deploy, a change to a financially significant system. Check: required reviews with author ≠ approver; environment reviewers exclude the author ("prevent self-review"); bots that auto-approve don't count as an independent reviewer.
- **SOD2** — developers don't have write access to production data or production infrastructure in their daily role; break-glass access is time-bound and logged.
- **SOD3** — in the application: a user can't both create and approve a financial transaction, refund, write-off, credit-limit change or price change (see SOX-MC); an admin can't edit their own permissions.
- **SOD4** — a single CI token or service account can't both merge and deploy and change protection rules; workflow `permissions:` least privilege.

## SOX-AC — Access to programs and data

- **AC1** — authentication for every user and service; unique IDs; MFA for administrators and for production access.
- **AC2** — role-based authorisation on every endpoint, job and tool that reads or changes financial data; deny by default.
- **AC3** — provisioning and de-provisioning are traceable (who granted which role, when, approved by whom); periodic access reviews possible (a way to list who has which role).
- **AC4** — privileged and service accounts: no shared credentials, no hard-coded secrets, rotation supported.
- **AC5** — direct database access to financial tables restricted; application DB user can't alter audit tables (see SOX-AT).

## SOX-OPS — Computer operations

- **OPS1** — scheduled jobs that post, bill, accrue, reconcile or report: failures are detected and alerted (not swallowed), jobs are idempotent and safely re-runnable, and each run records start, end, counts and outcome.
- **OPS2** — backups of financial data exist and restore is tested; point-in-time recovery enabled on financial tables (e.g. DynamoDB PITR, RDS automated backups).
- **OPS3** — incident and problem records link to the changes that fixed them.
- **OPS4** — time: UTC timestamps, synchronised clocks; period boundaries (month/quarter end, fiscal calendar, time zones) handled explicitly.

## SOX-AT — Audit trail of financial data

- **AT1** — every create, change and delete of a financially significant record (transactions, balances, invoices, subscriptions, prices, credit limits, refunds, journal entries) writes an audit entry: who (authenticated user or service), when (UTC), what (entity, id), before and after values, why (reason/ticket where applicable), and from where (request id, IP/service).
- **AT2** — the audit trail is **append-only and tamper-evident**: no update/delete path in code; DB permissions deny UPDATE/DELETE to the app user, or a WORM/object-lock store, or hash-chained entries; writes in the same transaction as the business change (or an outbox) so neither can happen without the other.
- **AT3** — financial records are not hard-deleted; corrections are reversing entries or new versions, never in-place overwrites of posted amounts.
- **AT4** — audit entries can't be switched off by configuration without that change itself being audited (cf. PCI 10.2.1.6).
- **AT5** — audit entries contain no secrets or unnecessary PII (link by id).

## SOX-CALC — Accuracy of financial calculations

- **CALC1** — money uses exact decimal types (`BigDecimal`, `decimal.Decimal`, integer minor units), never `float`/`double`; amounts carry a currency; no mixing currencies without explicit conversion with a recorded rate and timestamp.
- **CALC2** — rounding mode and scale are explicit and consistent (e.g. `RoundingMode.HALF_EVEN`, scale 2 or per-currency minor units); allocations and splits distribute the remainder so totals balance.
- **CALC3** — `BigDecimal` compared with `compareTo`, not `equals`; constructed from strings, not doubles (`new BigDecimal(0.1)` is wrong).
- **CALC4** — idempotency on postings and payments (idempotency key, unique constraint) so retries can't double-post; concurrency control (optimistic locking/versions, conditional writes) so concurrent updates can't lose a change to a balance.
- **CALC5** — calculations that drive revenue, fees, interest or credit decisions have tests with known-answer cases, boundaries and period edges.
- **CALC6** — input validation on amounts: sign, range, scale, currency allow-list; no negative refunds, no zero-amount bypasses.

## SOX-MC — Maker-checker and authorisation

- **MC1** — high-risk financial actions (manual adjustments, refunds over a threshold, write-offs, credit-limit or price changes, vendor/bank-detail changes) require a second, different user's approval, enforced server-side.
- **MC2** — approval limits by role are configuration under change control, and checked in code.
- **MC3** — the approver sees the final values (no edit after approval without re-approval).

## SOX-INT — Interfaces and completeness

- **INT1** — data feeds between systems (billing → ledger, payment processor webhooks → subscriptions, files to the GL) are complete and accurate: record counts and control totals, sequence or batch IDs, duplicate detection, a dead-letter path with alerting rather than silent drops.
- **INT2** — webhooks verified (signature, timestamp, replay protection) and processed idempotently.
- **INT3** — a reconciliation (internal records vs processor/bank/ledger) exists and breaks are reported.

## SOX-RPT — Reports and end-user computing

- **RPT1** — reports used for financial decisions or close come from controlled queries in the repo (tested), with parameters and run time recorded; not ad-hoc spreadsheets fed by manual exports.
- **RPT2** — report completeness: filters, period boundaries and time zones tested; totals reconcile to the source.

## SOX-RET — Record retention

- **RET1** — financial records and their audit trails retained for the required period — commonly **7 years** (SOX §802 sets 7 years for audit workpapers; SEC Rule 17a-4 and tax rules drive similar periods; confirm with the business). TTLs and purge jobs must not delete them early.
- **RET2** — conflicts with privacy erasure are resolved by keeping the financial record with minimal identifying data (legal-hold exception) and documenting why.
- **RET3** — CI/CD evidence (PR reviews, build and deploy logs) kept long enough for the audit period, or exported.

## SOX-EVD — Evidence

- Prefer machine-generated evidence over screenshots: export branch protection and rulesets (`gh api`), PR review history (`gh pr list --state merged --search "merged:>=<period start>" --limit 1000 --json number,author,reviews,mergedBy,mergeCommit`; the default limit is 30), deployment history (`gh api repos/{owner}/{repo}/deployments`), workflow run logs.
- A check for unreviewed changes: every commit on `main` since the last audit maps to a merged PR with an approving review by someone other than the author.

## Sources

- Sarbanes-Oxley Act of 2002, §§302, 404, 802; SEC final rule 33-8238 (ICFR).
- PCAOB AS 2201, *An Audit of Internal Control Over Financial Reporting* (ITGCs and application controls).
- COSO *Internal Control — Integrated Framework* (2013), principle 11 (technology general controls); ISACA COBIT 2019 (BAI06 managed IT changes, DSS05/DSS06).
- ISACA, *IT Control Objectives for Sarbanes-Oxley*, 3rd ed.
- Secureframe, "SOX ITGC": https://secureframe.com/blog/sox-itgc
- SafePaaS, "Key change management controls auditors look for in SOX ITGC audits": https://www.safepaas.com/itgc/key-change-management-controls-auditors-look-for-in-sox-itgc-audits/
- Harness, "SOX Compliance for Software Delivery": https://www.harness.io/harness-devops-academy/sox-compliance-for-software-delivery-explained
- Liquibase, "SOX compliance for database change management": https://www.liquibase.com/resources/guides/sox-compliance-for-database-change-management-best-practices
- GitHub Docs: protected branches, rulesets, deployment environments (required reviewers, prevent self-review).
