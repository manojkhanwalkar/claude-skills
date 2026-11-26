# Running Lighthouse and Lighthouse CI

Lighthouse 13 (October 2025) needs Node 22.19 or later. It kept the scoring but replaced many audits with **insight audits** (shared with Chrome DevTools' Performance panel) and removed others; the old ids are gone from the JSON. Read audit ids from the report you get; don't hard-code old ones.

## One-off runs (CLI)

Ask before the first `npx` (it downloads Lighthouse) unless the project already depends on it.

```bash
npm run build && npm run preview -- --port 4173 &            # the project's own prod build and server
npx lighthouse@13 http://localhost:4173/ \
  --output=json --output=html --output-path=./.lighthouseci/home-mobile \
  --chrome-flags="--headless=new" --quiet                    # mobile preset, throttled (default)
npx lighthouse@13 http://localhost:4173/ --preset=desktop \
  --output=json --output-path=./.lighthouseci/home-desktop.json --chrome-flags="--headless=new" --quiet
```

- Three runs per page and preset; keep the median by performance score (or by the metric under study). `lhci collect --numberOfRuns=3` does this for you.
- `--only-categories=performance` speeds up iterations; run all categories once at the end so an accessibility or best-practices regression shows.
- Same machine, same build, nothing else heavy running; note the Lighthouse and Chrome versions in the report.
- Reading the JSON: `categories.performance.score`, `audits['largest-contentful-paint'].numericValue`, `audits['total-blocking-time']`, `audits['cumulative-layout-shift']`, `audits['first-contentful-paint']`, `audits['speed-index']`, `audits['total-byte-weight']`; the LCP element and its phases are in the LCP breakdown insight; per-resource savings in each insight's `details`.

```bash
jq '{score: .categories.performance.score, lcp: .audits["largest-contentful-paint"].numericValue,
     tbt: .audits["total-blocking-time"].numericValue, cls: .audits["cumulative-layout-shift"].numericValue,
     bytes: .audits["total-byte-weight"].numericValue,
     failing: [.audits | to_entries[] | select(.value.score != null and .value.score < 0.9) | .key]}' \
  .lighthouseci/home-mobile.report.json
```

## Fold map

Lighthouse's viewports: mobile 412 × 823 (device scale factor 1.75), desktop 1350 × 940. When the project already has Playwright (or Puppeteer), this lists every image with its position and whether it is above the fold:

```js
// fold-map.mjs — node fold-map.mjs http://localhost:4173/
import { chromium } from 'playwright';
const url = process.argv[2];
const browser = await chromium.launch();
for (const [name, viewport] of [['mobile', { width: 412, height: 823 }], ['desktop', { width: 1350, height: 940 }]]) {
  const page = await browser.newPage({ viewport });
  await page.goto(url, { waitUntil: 'load' });
  const rows = await page.$$eval('img, [style*="background-image"], iframe, video', (els, h) => els.map(e => {
    const r = e.getBoundingClientRect();
    return { tag: e.tagName, src: e.currentSrc || e.src || '', top: Math.round(r.top), w: Math.round(r.width),
             natural: e.naturalWidth || null, loading: e.getAttribute('loading'), above: r.top < h && r.bottom > 0 };
  }), viewport.height);
  console.log(name, JSON.stringify(rows, null, 1));
  await page.close();
}
await browser.close();
```

An element above the fold on either viewport is treated as above the fold. `natural` versus rendered `w` (× device pixel ratio) shows oversized images. Keep the script out of the repository unless `--ci` adds it as a test.

## Lighthouse CI (`--ci`)

Ask before adding it: it is a new dev dependency and a new workflow.

`lighthouserc.json`:

```json
{
  "ci": {
    "collect": {
      "staticDistDir": "./dist",
      "url": ["http://localhost/", "http://localhost/products"],
      "numberOfRuns": 3,
      "settings": { "chromeFlags": "--headless=new" }
    },
    "assert": {
      "assertions": {
        "categories:performance": ["error", { "minScore": 0.9 }],
        "categories:accessibility": ["error", { "minScore": 0.9 }],
        "largest-contentful-paint": ["error", { "maxNumericValue": 2500 }],
        "total-blocking-time": ["error", { "maxNumericValue": 200 }],
        "cumulative-layout-shift": ["error", { "maxNumericValue": 0.1 }],
        "resource-summary:script:size": ["error", { "maxNumericValue": 300000 }],
        "resource-summary:image:size": ["warn", { "maxNumericValue": 500000 }],
        "resource-summary:total:size": ["error", { "maxNumericValue": 1200000 }]
      }
    },
    "upload": { "target": "filesystem", "outputDir": "./.lighthouseci" }
  }
}
```

- A server-rendered app uses `"startServerCommand": "npm run start"` and full URLs instead of `staticDistDir`.
- Set each limit just under today's median so the build passes now, then tighten as fixes land; a budget that fails on day one gets switched off.
- `aggregationMethod` defaults to the median for performance assertions when `numberOfRuns` > 1.
- `upload.target: "temporary-public-storage"` publishes reports to a public URL: only with the user's approval.
- Add `.lighthouseci/` to `.gitignore`.

`.github/workflows/lighthouse.yml` (pin each action to the commit SHA of its current release; the tags below are placeholders to resolve, never commit them unpinned):

```yaml
name: Lighthouse
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  lighthouse:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@<sha>        # vX
      - uses: actions/setup-node@<sha>      # vX
        with: { node-version: 22, cache: npm }
      - run: npm ci
      - run: npm run build
      - run: npx --yes @lhci/cli@<version> autorun
      - if: always()
        uses: actions/upload-artifact@<sha> # vX
        with: { name: lighthouse-reports, path: .lighthouseci, retention-days: 14 }
```

Add `Lighthouse` to the repo's `artifact-cleanup.yml` `workflows:` list when that file exists, and propose it as a required check only after it has been green for a few runs.
