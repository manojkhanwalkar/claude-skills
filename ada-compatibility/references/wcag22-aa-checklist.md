# WCAG 2.2 Level A + AA: Developer Checklist

All 55 Level A and AA success criteria of WCAG 2.2 (31 A, 24 AA; 4.1.1 Parsing was removed in 2.2), grouped by what a developer touches. Each item gives what to check, the usual fix, and false positives. **New in 2.2** marks the six A/AA additions. Use the SC number in findings.

## Contents
1. Structure and semantics
2. Names, labels and text alternatives
3. Keyboard
4. Focus
5. Colour, contrast and visual presentation
6. Zoom, reflow and responsive layout
7. Forms, errors and input
8. Dynamic content, state and announcements
9. Time, motion and media
10. Pointer and touch
11. Navigation and consistency
12. Authentication
13. Mobile apps (iOS, Android, React Native, Flutter)
14. Testing recipes
15. Coverage map (every A/AA criterion → section)
16. Sources

---

## 1. Structure and semantics

- **1.3.1 Info and Relationships (A):**
  - Structure shown visually is also in markup: real headings `<h1>`–`<h6>`, lists `<ul>/<ol>/<dl>`, tables with `<th scope>` and `<caption>`, `<fieldset>/<legend>` for radio and checkbox groups, and landmarks (`<header> <nav> <main> <aside> <footer>`, one `<main>`).
  - Divs styled to look like headings or tables are findings.
  - Don't use layout tables. Don't use `<br>` lists.
  - Heading levels shouldn't skip (h2 → h4) without reason.
- **1.3.2 Meaningful Sequence (A):** DOM order matches reading order. CSS `order`, `flex-direction: row-reverse`, absolute positioning and grid placement can scramble it for screen readers and keyboard users.
- **1.3.3 Sensory Characteristics (A):** instructions don't rely only on shape, colour, size, position or sound ("press the round green button", "see the box on the right").
- **2.4.2 Page Titled (A):** every page or route has a unique, descriptive `<title>`. SPAs update `document.title` on route change.
- **3.1.1 Language of Page (A):** `<html lang="en">` (or the correct code).
- **3.1.2 Language of Parts (AA):** passages in another language get their own `lang`.
- **4.1.2 Name, Role, Value (A):**
  - Every UI component exposes a correct role, an accessible name, and its states and values (`aria-expanded`, `aria-pressed`, `aria-checked`, `aria-selected`, `aria-current`, `aria-invalid`, `aria-disabled`).
  - Custom widgets follow the ARIA APG pattern.
  - Don't add a `role` that contradicts the element (`<button role="link">`), or redundant roles.
  - `aria-hidden="true"` is never on focusable content or its ancestors.

**First rule of ARIA:** use native HTML. Bad ARIA is worse than none.

## 2. Names, labels and text alternatives

- **1.1.1 Non-text Content (A):**
  - **Images:** every `<img>` has `alt`. Informative images say what matters in context; decorative ones get `alt=""` (or are CSS backgrounds); functional images (a logo link, an icon button) describe the action or destination.
  - **SVGs:** `role="img"` plus `<title>` or `aria-label` when meaningful, `aria-hidden="true"` when decorative.
  - **Icon fonts:** `aria-hidden` plus a visible or `sr-only` label.
  - **Charts:** a text summary or data table.
  - **CAPTCHAs:** an alternative modality (see 3.3.8).
- **2.4.4 Link Purpose (In Context) (A):** link text, with its context, says where it goes. Repeated "Click here", "More" or "Read more" links need distinguishing text (visually hidden text or `aria-describedby`). Icon-only links need a name.
- **2.4.6 Headings and Labels (AA):** headings and labels describe their topic or purpose.
- **2.5.3 Label in Name (A):** the accessible name contains the visible label text, ideally starting with it. A button showing "Send" must not have `aria-label="Submit form"`. Voice-control users say what they see.
- **Accessible-name computation order:**
  - `aria-labelledby`, then `aria-label`, then the native label (`<label>`, `alt`, `<caption>`, `<legend>`), then text content, then `title` (a weak last resort).
  - Use `aria-label` only where no visible label exists.
  - `placeholder` is not a label.

## 3. Keyboard

- **2.1.1 Keyboard (A):** everything works by keyboard.
  - Click handlers on non-interactive elements (`div`, `span`, `li`, `img`) are findings. Use `<button>`, or add `role`, `tabindex="0"` and Enter/Space handlers.
  - Use `onClick` on `<button>`, not `onMouseDown`. Avoid hover-only menus.
  - Drag and drop needs a keyboard alternative.
  - Custom widgets implement the APG keyboard model: arrow keys within composites (tabs, menus, listbox, grid), Escape closes, Home/End.
- **2.1.2 No Keyboard Trap (A):** focus can always leave a component (embedded editors, iframes, modals). A modal keeps focus *inside* while open, but Escape or a close button must work.
- **2.1.4 Character Key Shortcuts (A):** single-key shortcuts (no modifier) can be turned off or remapped, or only work when their component has focus.
- **2.4.1 Bypass Blocks (A):** a "Skip to main content" link as the first focusable element, plus landmarks and headings.
- **2.4.3 Focus Order (A):**
  - Tab order follows meaning. No positive `tabindex`.
  - Opening a dialog moves focus into it; closing it returns focus to the trigger.
  - After route changes in an SPA, focus moves to the new page's heading or main region.
  - Off-screen or hidden content (closed drawers, `visibility: hidden`) isn't focusable. Use `inert` for content behind a modal.

## 4. Focus

- **2.4.7 Focus Visible (AA):** a visible focus indicator on every focusable element.
  - `outline: none` or `outline: 0` without a replacement is a finding.
  - Use `:focus-visible { outline: 2px solid <token>; outline-offset: 2px; }`.
- **2.4.11 Focus Not Obscured (Minimum) (AA, new in 2.2):** a focused element isn't entirely hidden by author content (sticky headers, footers, cookie banners, chat widgets). Fix with `scroll-padding-top` / `scroll-margin` equal to the sticky header's height, and non-overlapping banners.
- **1.4.11 Non-text Contrast (AA):** focus indicators reach 3:1 against what's next to them (and see section 5).
- **3.2.1 On Focus (A):** receiving focus doesn't trigger a change of context (no navigation, submit or popup opening on focus).

## 5. Colour, contrast and visual presentation

- **1.4.1 Use of Colour (A):** colour isn't the only way to convey meaning. Errors need an icon or text; links in body text need an underline (or 3:1 contrast with the surrounding text plus a non-colour cue on hover and focus); chart series need patterns or labels.
- **1.4.3 Contrast (Minimum) (AA):** text needs **4.5:1**, or **3:1** for large text (≥ 24 px, or ≥ 18.66 px bold). This includes placeholder text, disabled-looking enabled text, and text over images or gradients (check the worst spot).
  - Logos and truly disabled controls are exempt.
  - Compute from design tokens: relative luminance L = 0.2126 R + 0.7152 G + 0.0722 B (linearised); ratio = (L1 + 0.05) / (L2 + 0.05).
- **1.4.11 Non-text Contrast (AA):** **3:1** for UI component boundaries needed to identify them (input borders, toggles, checkboxes), for states (selected, checked), focus rings and meaningful graphics (chart lines, icons without text).
- **1.4.5 Images of Text (AA):** use real text, not pictures of text (logos excepted).
- **1.4.12 Text Spacing (AA):** no loss of content when users set line-height 1.5, paragraph spacing 2×, letter-spacing 0.12em and word-spacing 0.16em. Avoid fixed heights on text containers, and `overflow: hidden` that clips text.
- **1.4.13 Content on Hover or Focus (AA):** tooltips and popovers that appear on hover or focus are:
  - dismissible (Escape, without moving the pointer or focus);
  - hoverable (the pointer can move onto them);
  - persistent (they stay until dismissed or no longer relevant).

## 6. Zoom, reflow and responsive layout

- **1.4.4 Resize Text (AA):** text works at 200% zoom.
  - Don't block zoom: no `user-scalable=no`, no `maximum-scale` below 2.
  - Use `rem` or `em` for font sizes, not fixed `px` containers that clip.
- **1.4.10 Reflow (AA):** content works at 320 CSS px width (400% zoom on 1280 px) without two-dimensional scrolling. Data tables, maps and code are exempt. Check fixed-width containers, `white-space: nowrap`, and wide images without `max-width: 100%`.
- **1.3.4 Orientation (AA):** don't lock to portrait or landscape unless it's essential.

## 7. Forms, errors and input

- **3.3.2 Labels or Instructions (A):**
  - Every field has a visible, persistent label, not just a placeholder.
  - Required fields are indicated in text or a symbol explained once, plus `required` / `aria-required`.
  - State format hints ("MM/DD/YYYY") up front, and connect them with `aria-describedby`.
- **1.3.5 Identify Input Purpose (AA):** personal-data fields carry the right `autocomplete` token (`name`, `given-name`, `email`, `tel`, `street-address`, `postal-code`, `cc-number`, `username`, `current-password`, `new-password`, `one-time-code`, `bday`…).
- **3.3.1 Error Identification (A):** errors are described in text, naming the field, and tied to it (`aria-invalid="true"` plus `aria-describedby` pointing to the message).
  - On submit, move focus to the first invalid field or to an error summary with links.
  - The summary or inline error is announced (a `role="alert"` region or focus).
- **3.3.3 Error Suggestion (AA):** say how to fix it ("Enter a 5-digit ZIP code"), unless that would weaken security (don't say which of user id or password was wrong).
- **3.3.4 Error Prevention (Legal, Financial, Data) (AA):** for legal commitments, financial transactions, account deletion and data changes, the submission must be reversible, checked, or confirmed. Example: a review step, a "type DELETE to confirm" step, or re-authentication.
- **3.3.7 Redundant Entry (A, new in 2.2):** in one process, don't ask again for information already given. Auto-fill it or offer it for selection ("Billing same as shipping"). Exceptions: security (re-entering a password) and content that's no longer valid.
- **3.2.2 On Input (A):** changing a field doesn't cause an unexpected change of context (no auto-submit on select change, no new window). If it must, warn beforehand.
- **2.5.2 Pointer Cancellation (A):** actions fire on pointer **up** (`click`), not down, so users can slide off to cancel.

## 8. Dynamic content, state and announcements

- **4.1.3 Status Messages (AA):** messages that don't take focus are announced via live regions:
  - `role="status"` (polite) for "Saved", "3 results", "Loading…";
  - `role="alert"` (assertive) only for errors and urgent messages.
  - The region must exist in the DOM *before* its text changes. Inserting a new element with `role="alert"` is less reliable than updating an existing one.
- **Expanding, selecting and loading:**
  - Disclosure buttons carry `aria-expanded` and `aria-controls`.
  - Tabs carry `aria-selected`; toggles `aria-pressed`; the current page `aria-current="page"`.
  - Loading regions carry `aria-busy`.
- **Infinite scroll, toasts and auto-updates:** toasts that vanish must stay long enough (see 2.2.1), be announced, and not steal focus.
- **Modals and dialogs:**
  - Use `<dialog>` with `showModal()`, or `role="dialog"` with `aria-modal="true"`, labelled by its heading.
  - Move focus inside on open. Escape closes. Return focus to the trigger on close. Make the background `inert`.
- **SPA route changes:** update the title, move focus to the new content's heading (or announce it), and keep the browser history working.

## 9. Time, motion and media

- **2.2.1 Timing Adjustable (A):** session timeouts and timed actions can be turned off, adjusted, or extended: warn at least 20 seconds before, and offer "Stay signed in" with a single action. A security idle timeout may apply, but give a warning with a way to extend it where possible.
- **2.2.2 Pause, Stop, Hide (A):** anything that moves, blinks or scrolls for more than 5 s (carousels, marquees, animations), or auto-updates, has pause, stop or hide controls.
- **2.3.1 Three Flashes or Below Threshold (A):** nothing flashes more than 3 times a second.
- **Reduced motion (best practice, also 2.3.3 AAA):** honour `@media (prefers-reduced-motion: reduce)` for parallax, large transitions and auto-playing animation.
- **1.4.2 Audio Control (A):** audio that plays automatically for more than 3 s can be paused or muted. Avoid `autoplay` with sound.
- **1.2.1 Audio-only and Video-only (Prerecorded) (A):** provide a transcript, or an audio or text alternative.
- **1.2.2 Captions (Prerecorded) (A)** and **1.2.4 Captions (Live) (AA):** synchronised captions (`<track kind="captions">`) for video with speech.
- **1.2.3 Audio Description or Media Alternative (A)** and **1.2.5 Audio Description (Prerecorded) (AA):** audio description of important visual-only information in prerecorded video.
- **Media players:** keyboard-operable controls with names. Use a player that supports captions.

## 10. Pointer and touch

- **2.5.1 Pointer Gestures (A):** multipoint or path-based gestures (pinch, swipe, draw) have a single-pointer alternative (buttons).
- **2.5.4 Motion Actuation (A):** shake or tilt actions have a UI alternative, and motion can be turned off.
- **2.5.7 Dragging Movements (AA, new in 2.2):** anything done by dragging (sliders, sortable lists, map panning, kanban) can also be done with single taps or clicks: up/down buttons, "Move to…" menus, or click-to-place.
- **2.5.8 Target Size (Minimum) (AA, new in 2.2):** pointer targets are at least **24×24 CSS px**, or have enough spacing (a 24 px circle centred on each doesn't overlap another target).
  - Exceptions: an equivalent control elsewhere, inline links in text, user-agent default controls, and cases where the size is essential.
  - Aim for 44×44 on touch.

## 11. Navigation and consistency

- **2.4.5 Multiple Ways (AA):** more than one way to find a page in a site (navigation, search, sitemap), except for steps in a process.
- **3.2.3 Consistent Navigation (AA):** repeated navigation appears in the same relative order on every page.
- **3.2.4 Consistent Identification (AA):** the same function has the same name and icon everywhere.
- **3.2.6 Consistent Help (A, new in 2.2):** help mechanisms (contact details, a chat or help link, an FAQ) appear in the same relative place on every page that has them.

## 12. Authentication

- **3.3.8 Accessible Authentication (Minimum) (AA, new in 2.2):** no cognitive function test (remembering a password, transcribing a code, solving a puzzle) is required to log in unless there is an alternative or help.
  - **Allow** paste and password managers in password and one-time-code fields: no `onpaste` blocking, correct `autocomplete="current-password"` / `"one-time-code"`, and don't split codes into several inputs that defeat paste.
  - **Offer** passkeys or WebAuthn, email magic links, or "show password".
  - **Avoid** puzzle CAPTCHAs without an alternative. Object recognition ("pick the bicycles") is allowed at AA but not at AAA.
- **2.2.1** applies to login timeouts too.

## 13. Mobile apps

The same criteria apply, through the platform accessibility APIs:

- **iOS (SwiftUI/UIKit):**
  - Use `accessibilityLabel`, `accessibilityHint`, `accessibilityTraits` and `.accessibilityElement(children:)` grouping.
  - Support Dynamic Type (`.font(.body)`, no fixed sizes).
  - Touch targets ≥ 44×44 pt.
  - Test with VoiceOver, Voice Control and Reduce Motion.
- **Android (Compose/Views):**
  - Use `contentDescription` (null for decorative), `Modifier.semantics { }`, `Role`, `stateDescription`, and `mergeDescendants`.
  - Size text in `sp`. Touch targets ≥ 48×48 dp (`minimumInteractiveComponentSize`).
  - Test with TalkBack, Switch Access and the Accessibility Scanner. Use Espresso `AccessibilityChecks.enable()` in tests.
- **React Native:** `accessible`, `accessibilityLabel`, `accessibilityRole`, `accessibilityState`, `accessibilityHint`, `importantForAccessibility`.
- **Flutter:** `Semantics`, `semanticsLabel`, `ExcludeSemantics`, and `MergeSemantics`. Test with `meetsGuideline(androidTapTargetGuideline / iOSTapTargetGuideline / textContrastGuideline / labeledTapTargetGuideline)`.

## 14. Testing recipes

- **Component tests (React, Vue, Svelte):**
  ```js
  import { axe } from 'jest-axe';            // or vitest-axe
  const { container } = render(<SignupForm />);
  expect(await axe(container)).toHaveNoViolations();
  expect(screen.getByRole('textbox', { name: /email/i })).toBeRequired();
  ```
- **Page tests (Playwright):**
  ```js
  import AxeBuilder from '@axe-core/playwright';
  const results = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']).analyze();
  expect(results.violations).toEqual([]);
  ```
  Keyboard test:
  ```js
  await page.keyboard.press('Tab'); await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
  ```
- **Cypress:** `cy.injectAxe(); cy.checkA11y(null, { runOnly: ['wcag2a','wcag2aa','wcag21aa','wcag22aa'] })`.
- **CLI or CI without a test suite:** `npx pa11y-ci` (runner `axe`, standard `WCAG2AA`) or `npx @axe-core/cli <urls> --exit`.
- **Server-rendered pages in Java:** `org.jsoup` assertions on the rendered HTML (each `input` has a `label[for]` or `aria-label`; `html[lang]`; each `img[alt]`). Also `com.deque.html.axe-core:playwright` or `selenium` if a browser runs in CI.
- **Linters:** `eslint-plugin-jsx-a11y` (recommended or strict), `eslint-plugin-vuejs-accessibility`, `@angular-eslint/template` accessibility rules, `stylelint-a11y`.
- **Gate on new violations:** fail CI on any new violation. If legacy debt exists, baseline the known ones explicitly (a reviewed allow-list with expiry), never wholesale.
- **Manual pass for every UI PR that changes interaction:**
  - keyboard only: Tab, Shift+Tab, Enter, Space, Escape, arrow keys;
  - a screen reader: VoiceOver + Safari, NVDA + Firefox or Chrome;
  - 200% zoom and 320 px width;
  - `prefers-reduced-motion`;
  - forced colours / Windows High Contrast (`@media (forced-colors: active)`).

## 15. Coverage map

| Section | Success criteria |
|---|---|
| 1 Structure | 1.3.1, 1.3.2, 1.3.3, 2.4.2, 3.1.1, 3.1.2, 4.1.2 |
| 2 Names | 1.1.1, 2.4.4, 2.4.6, 2.5.3 |
| 3 Keyboard | 2.1.1, 2.1.2, 2.1.4, 2.4.1, 2.4.3 |
| 4 Focus | 2.4.7, 2.4.11, 3.2.1 |
| 5 Colour and presentation | 1.4.1, 1.4.3, 1.4.5, 1.4.11, 1.4.12, 1.4.13 |
| 6 Zoom and reflow | 1.3.4, 1.4.4, 1.4.10 |
| 7 Forms | 1.3.5, 2.5.2, 3.2.2, 3.3.1, 3.3.2, 3.3.3, 3.3.4, 3.3.7 |
| 8 Dynamic content | 4.1.3 |
| 9 Time, motion, media | 1.2.1, 1.2.2, 1.2.3, 1.2.4, 1.2.5, 1.4.2, 2.2.1, 2.2.2, 2.3.1 |
| 10 Pointer | 2.5.1, 2.5.4, 2.5.7, 2.5.8 |
| 11 Navigation | 2.4.5, 3.2.3, 3.2.4, 3.2.6 |
| 12 Authentication | 3.3.8 |

That is 31 Level A + 24 Level AA = 55 criteria.

## 16. Sources

**Standards and law**
- W3C, *Web Content Accessibility Guidelines (WCAG) 2.2* (Recommendation, Oct 2023): https://www.w3.org/TR/WCAG22/ ; "What's New in WCAG 2.2": https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/ ; *How to Meet WCAG (Quick Reference)*.
- W3C, *ARIA Authoring Practices Guide (APG)*: https://www.w3.org/WAI/ARIA/apg/ ; *Using ARIA* (the five rules of ARIA).
- DOJ, *Nondiscrimination on the Basis of Disability; Accessibility of Web Information and Services of State and Local Government Entities* (28 CFR part 35, subpart H, April 2024), and the April 2026 interim final rule extending the deadlines: https://www.adatitleiii.com/2026/04/doj-extends-ada-title-ii-website-accessibility-deadlines-for-governmental-entities-but-litigation-and-compliance-risks-remain/ ; https://titleii.org/deadlines
- DOJ, *Guidance on Web Accessibility and the ADA* (March 2022): https://www.ada.gov/resources/web-guidance/
- FTC v. accessiBe (2025 order on overlay claims); Level Access, "Title III lawsuits": https://www.levelaccess.com/blog/title-iii-lawsuits-10-big-companies-sued-over-website-accessibility/
- Section 508 (36 CFR 1194, the 2017 refresh), which incorporates WCAG 2.0 AA. EN 301 549 v3.2.1 (EU).

**Implementation guides**
- Level Access, "WCAG 2.2 AA summary and checklist": https://www.levelaccess.com/blog/wcag-2-2-aa-summary-and-checklist-for-website-owners/
- BOIA, "WCAG 2.2 A/AA checklist": https://www.boia.org/wcag-2.2aa-checklist
- Deque axe-core rules and coverage; University of Arizona, "Accessibility testing in CI/CD": https://accessibility.arizona.edu/web-apps/cicd-testing
- Apple Human Interface Guidelines (Accessibility); Android Developers, "Make apps more accessible"; Flutter accessibility testing guide.
