# Similar Laws Outside the EU — What Differs for Engineers

Build to the GDPR baseline in `gdpr.md`, then add the deltas below for each region the product serves. Thresholds and dates: `applicability.md`.

## Contents
- Handling many regimes at once
- US: CCPA/CPRA
- US: other state comprehensive privacy laws
- US: sector laws (COPPA, GLBA, FCRA, HIPAA, BIPA, Washington MHMDA)
- UK: UK GDPR + DUAA 2025, PECR, Online Safety Act, DMCC Act
- Brazil LGPD
- Canada PIPEDA and Quebec Law 25
- India DPDP Act 2023 and Rules 2025
- China PIPL
- Others (Japan APPI, Singapore PDPA, Australia Privacy Act, South Korea PIPA)
- Sources

---

## Handling many regimes at once

- Model **purposes and consents per jurisdiction** in one consent/preferences service, not per feature. Store the user's region (from account, not only IP) and the rule set applied.
- Support both **opt-in** (EU/UK, sensitive data under US state laws) and **opt-out** (US "sale/share/targeted advertising") semantics, plus **universal opt-out signals** (`Sec-GPC: 1`).
- One DSR pipeline (access, delete, correct, port, opt-out) with per-law deadlines (GDPR 1 month; CCPA 45 days; LGPD 15 days for full access; DPDP per Rules) and identity verification.
- One data map that records storage region per store, to answer localisation (PIPL, some DPDP restrictions) and transfer questions.

## US: CCPA/CPRA (California)

- Rights: know/access (incl. specific pieces), delete, **correct**, **opt out of sale and sharing** (sharing = cross-context behavioural advertising), **limit use of sensitive personal information** (SSN, driver's licence, passport, account log-in, financial account + credentials, precise geolocation, racial/ethnic origin, religion, union membership, mail/email/text contents, genetic, biometric, health, sex life/orientation, citizenship/immigration status, neural data), non-discrimination.
- UI: "Do Not Sell or Share My Personal Information" and "Limit the Use of My Sensitive Personal Information" links (or a combined alternative opt-out link), or honour opt-out preference signals in a frictionless way; notice at collection.
- **GPC must be honoured** as an opt-out of sale/sharing (and, per regs, shown as processed).
- Service-provider contracts restrict use; third parties notified of deletion and opt-outs.
- CPPA regulations (2025): **automated decision-making technology (ADMT)** used for significant decisions (financial or lending services, housing, education, employment, healthcare) → pre-use notice, opt-out or appeal with human review, access to information about the logic — compliance from 2027; **risk assessments** for high-risk processing; **annual cybersecurity audits** phased by revenue from 2028.
- Dark patterns: consent obtained through dark patterns isn't consent; symmetry in choices required.
- 45-day response window (extendable once by 45).

## US: other state comprehensive privacy laws

Virginia, Colorado, Connecticut, Utah, Texas, Oregon, Montana, Iowa, Delaware, New Hampshire, New Jersey, Tennessee, Minnesota, Maryland, Indiana, Kentucky, Rhode Island, Nebraska (and more each year):
- Opt-out of targeted advertising, sale and profiling with legal or similarly significant effects; **opt-in consent for sensitive data** in most (Maryland: sensitive data processing only when strictly necessary; sale prohibited).
- **Universal opt-out mechanisms** (GPC) mandatory in CO, CT, TX, OR, MT, DE, NJ, NH, MN, MD and others.
- Data protection assessments for targeted ads, sale, sensitive data, profiling.
- Teen protections: opt-in for targeted ads/sale for 13–15 or under 18 (CT, OR, DE, NJ, MD…); some states' "age-appropriate design" codes.
- Appeals process for denied requests.

## US: sector laws

- **COPPA** (under 13): verifiable parental consent before collecting children's PI, including persistent identifiers for ads; 2025 amendments — separate consent for disclosure to third parties (incl. targeted ads), written data retention policy and deletion when no longer needed, written security program; compliance by 22 Apr 2026.
- **GLBA** (financial institutions): privacy notice and opt-out of sharing with non-affiliated third parties (Reg. P); Safeguards Rule security program (see `compliance-check`).
- **FCRA** (consumer reports, credit scores): permissible purpose before pulling a report; **adverse action notices** with the score used, key factors, bureau contact and dispute rights when credit is denied or terms worsened (ECOA/Reg. B also requires specific principal reasons — including when AI models drive the decision, per CFPB circulars); accuracy and dispute handling for furnishers.
- **State AI/ADMT laws**: Colorado SB 26-189 (from 1 Jan 2027; replaced the 2024 Colorado AI Act before it took effect) regulates automated decision-making technology that materially influences consequential decisions — notice, explanation and correction or appeal paths; check the statute's domains and duties. Same code checks as GDPR Art. 22 (`gdpr.md` G-ADM) and the CCPA ADMT rules.
- **HIPAA** (covered entities and business associates): flag and ask; don't treat health data casually even outside HIPAA (Washington My Health My Data Act: consent and a separate privacy policy for consumer health data, private right of action; Nevada and Connecticut similar).
- **Biometrics** (Illinois BIPA, Texas CUBI, Washington): written notice and consent before collecting face/voice/fingerprint templates; retention schedule; no sale. BIPA has a private right of action.

## UK: UK GDPR + Data (Use and Access) Act 2025, PECR, Online Safety Act, DMCC Act

- UK GDPR ≈ GDPR. DUAA 2025: "recognised legitimate interests" (e.g. security, crime prevention) without a balancing test; Art. 22 relaxed to allow solely automated decisions with safeguards (except special-category data); complaints-handling duty; some cookies (analytics, functionality, security) exempt from consent if users are told and can object; PECR fines raised to UK GDPR levels.
- **Age Appropriate Design Code** (Children's Code) for services likely to be accessed by under-18s: high-privacy defaults, geolocation off, no nudges, DPIA.
- **Online Safety Act 2023**: user-to-user and search services with UK users — illegal-content risk assessments and safety duties (in force 2025), children's risk assessments and **highly effective age assurance** for pornographic and certain harmful content (from 25 Jul 2025), user reporting and complaints, terms transparency.
- **DMCC Act 2024**: conduct requirements for firms with Strategic Market Status (similar to DMA); consumer-law enforcement by the CMA directly incl. **subscription contract rules** (clear pre-contract info, reminders, easy cancellation) and fake-review bans.

## Brazil LGPD

- GDPR-like; ten legal bases incl. **credit protection** (Art. 7(X)) — relevant to credit products; sensitive data stricter; DPO (encarregado) contact published; data subject requests — simplified answer immediately, full within 15 days; ANPD international transfer regulation (2024) with standard contractual clauses (mandatory adoption by Aug 2025); incident notification to ANPD within 3 working days.

## Canada PIPEDA and Quebec Law 25

- PIPEDA: meaningful consent (express for sensitive), purpose limitation, access and correction, breach reporting to the OPC and records of all breaches.
- **Quebec Law 25**: privacy by default (highest privacy settings by default; tracking/profiling/location features off by default and user-activated), PIA before transfers outside Quebec and for new systems, data portability (since Sep 2024), notice when a decision is made exclusively by automated processing + right to know factors and request human review, de-indexing, confidentiality incident register.

## India DPDP Act 2023 and Rules 2025

- Consent must be free, specific, informed, unconditional and unambiguous with a **clear affirmative action**, preceded by an itemised notice in plain language (English or Eighth-Schedule languages); withdrawal as easy as giving; consent managers (registered) may be used.
- Legitimate uses limited (no general legitimate-interest basis).
- **Children (< 18)**: verifiable parental consent; no tracking, behavioural monitoring or targeted advertising directed at children.
- Erasure when the purpose is served or consent withdrawn; Rules set retention/erasure periods for certain classes (e.g. large e-commerce, gaming, social media platforms erase after 3 years of inactivity with 48-hour advance notice).
- Security safeguards incl. encryption/masking, access control, logs retained ≥ 1 year; breach notice to the Board and each affected person.
- Rules notified Nov 2025 with phased commencement (most obligations ~18 months later); Significant Data Fiduciaries: DPIAs and audits, possible localisation of specified data.

## China PIPL

- Separate consent for sensitive PI, for providing PI to other handlers, for public disclosure and for **cross-border transfer**; transfers via CAC security assessment, standard contract filing, or certification (with 2024 exemptions/thresholds); localisation for critical information infrastructure operators and large volumes; PIPIA (impact assessment) before high-risk processing; automated decision-making must offer a non-personalised option and refuse-explanation rights; minors' data (< 14) sensitive.

## Others

- **Japan APPI**: consent for third-party provision and overseas transfers (with information about the destination country's regime); "personally referable information" (cookies/IDs) needs consent when the recipient will link it to a person. **Japan Mobile Software Competition Act** (fully in force Dec 2025): DMA-like rules for Apple/Google app stores, browsers and search.
- **Singapore PDPA**: consent and notification, DNC registry, mandatory breach notification (3 days to PDPC), data portability provisions.
- **Australia Privacy Act** (2024 amendments): automated-decision transparency in privacy policies (from Dec 2026), statutory tort for serious invasions of privacy, Children's Online Privacy Code in development.
- **South Korea PIPA** (2023 amendments): right to refuse/explanations for automated decisions, portability.

## Sources

- California: Cal. Civ. Code §1798.100 et seq.; CPPA regulations (Cal. Code Regs. tit. 11, §7000+), incl. 2025 ADMT, risk assessment and cybersecurity audit regulations: https://cppa.ca.gov/regulations/ ; Transcend, "Engineering implications of the CPRA": https://transcend.io/blog/engineering-implications-cpra
- Colorado SB 26-189 (2026): Skadden, "Colorado Repeals and Replaces Its AI Act": https://www.skadden.com/insights/publications/2026/06/colorado-repeals-and-replaces-its-ai-act
- IAPP US State Privacy Legislation Tracker: https://iapp.org/resources/article/us-state-privacy-legislation-tracker/
- FTC COPPA Rule amendments (2025); CFPB Circular 2022-03 and 2023-03 (adverse action with complex algorithms).
- UK: Data (Use and Access) Act 2025; ICO Children's Code; Ofcom Online Safety codes; DMCC Act 2024.
- Brazil LGPD (Law 13.709/2018) and ANPD Resolution CD/ANPD 19/2024 (international transfers).
- Quebec Act respecting the protection of personal information in the private sector (Law 25).
- India Digital Personal Data Protection Act 2023 and DPDP Rules 2025 (MeitY).
- China Personal Information Protection Law (2021) and CAC cross-border data rules (2024).
