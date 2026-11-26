# Sources

- Chrome for Developers, "What's new in Lighthouse 13" (insight audits replace old audits; removed audits; Node 22.19+): https://developer.chrome.com/blog/lighthouse-13-0
- Search Engine Journal on Lighthouse 13's insight-based audits: https://www.searchenginejournal.com/google-lighthouse-13-launches-with-insight-based-audits/558051/
- web.dev, "How the Core Web Vitals metrics thresholds were defined" (LCP 2.5 s, INP 200 ms, CLS 0.1 at the 75th percentile): https://web.dev/articles/defining-core-web-vitals-thresholds
- Lighthouse, "Properly size images" (rendered size × DPR, 4 KiB savings threshold; now in the image delivery insight): https://developer.chrome.com/docs/lighthouse/performance/uses-responsive-images/
- web.dev, "Serve images with correct dimensions": https://web.dev/articles/serve-images-with-correct-dimensions
- web.dev, "Optimize resource loading with the Fetch Priority API": https://web.dev/articles/fetch-priority
- Chrome for Developers, "Optimize image priority" (never lazy-load the LCP image; one high-priority image): https://developer.chrome.com/docs/modern-web-guidance/guides/performance/optimize-image-priority
- Chrome for Developers, LCP discovery insight: https://developer.chrome.com/docs/performance/insights/lcp-discovery
- web.dev, "Key performance issues" (images): https://web.dev/learn/images/performance-issues
- Chrome for Developers, "Use scheduler.yield() to break up long tasks" (Chrome and Edge 129, Firefox 142, Safari not supported: feature-detect): https://developer.chrome.com/blog/use-scheduler-yield
- Chrome for Developers, "Break up long tasks": https://developer.chrome.com/docs/modern-web-guidance/guides/performance/break-up-long-tasks
- Lighthouse CI configuration and assertions (`numberOfRuns`, `resource-summary` budgets, presets): https://github.com/GoogleChrome/lighthouse-ci/blob/main/docs/configuration.md , https://unlighthouse.dev/learn-lighthouse/lighthouse-ci/budgets
- treosh/lighthouse-ci-action (runs per URL, artifacts): https://github.com/treosh/lighthouse-ci-action
- Addy Osmani, "Use fetchpriority=high to load your LCP hero image sooner": https://addyosmani.com/blog/fetch-priority/
