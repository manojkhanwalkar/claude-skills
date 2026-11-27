# UI optimization checklist

Each item: what to look for, how to confirm, the fix. Fold rules in SKILL.md Phase 3 apply throughout.

## Images (usually the biggest win)

| Problem | Confirm | Fix |
|---|---|---|
| Heavy file (`image-heavy`) | Lighthouse "Improve image delivery" insight lists it with estimated savings | Resize, AVIF or WebP, quality 60-75 for photos; lossless (or SVG) for flat graphics and logos |
| Larger than displayed (`image-dimensions`) | Lighthouse flags an image when its rendered size (× device pixel ratio) would save at least 4 KiB | Serve at most displayed width × 2; `srcset` with width descriptors (`480w, 800w, 1200w, 1600w`) and an accurate `sizes` |
| Legacy format | PNG or JPEG photos | `<picture><source type="image/avif"><source type="image/webp"><img …></picture>`, or the framework image component; AVIF and WebP are supported in all current major browsers |
| Animated GIF (`gif-animation`) | Over about 100 KiB | `<video autoplay muted loop playsinline>` with MP4 or WebM, a poster frame |
| No dimensions (`img-no-size`) | CLS culprits insight names it | `width` and `height` attributes (intrinsic ratio), or CSS `aspect-ratio` |
| LCP image lazy-loaded | LCP element has `loading="lazy"`, or LCP "load delay" phase is large | Remove `loading="lazy"`; `fetchpriority="high"`; never both (`lazy-and-high`) |
| LCP image discovered late | LCP discovery insight: image set by JavaScript, a CSS background, or `data-src` lazy-load library | Put it in the initial HTML as `<img>`; or `<link rel="preload" as="image" fetchpriority="high" imagesrcset="…" imagesizes="…">` |
| Below-the-fold images eager (`img-loading-unset`) | Image box starts below the viewport (fold map) | `loading="lazy" decoding="async"`; drop JS lazy-load libraries in favour of the native attribute |
| Too many high-priority hints | Several `fetchpriority="high"` or preloads | One: the LCP image. If everything is high priority, nothing is |
| Icons as many small images | Dozens of icon requests | Inline SVG or an SVG sprite; icon fonts only if already used |
| Images served without caching | Response headers | Hashed filenames + `Cache-Control: public, max-age=31536000, immutable` |

Never drop `alt` text, captions or the visible crop the design relies on.

## Scripts: render-blocking and async

| Problem | Confirm | Fix |
|---|---|---|
| Blocking `<script src>` in `<head>` (`script-blocking`) | Render-blocking requests insight | `defer` (keeps order, runs after parse) for app code; `async` for independent tags; `type="module"` is deferred by default |
| Large initial bundle | JavaScript bytes on the landing route; unused JavaScript insight | Route-level code splitting; dynamic `import()` for below-the-fold and interaction-only UI (modals, editors, charts, maps); tree-shakeable imports (`whole-library`) |
| Legacy JavaScript to modern browsers | Legacy JavaScript insight (polyfills and transforms for features browsers already have) | Raise the build target (browserslist, Vite `build.target`), drop unneeded polyfills |
| Hydrating static content | Mostly static page with full client hydration | Server components, islands, partial or lazy hydration (`client:visible`, `client:idle`, Nuxt lazy hydration, Angular `@defer` + incremental hydration) |
| Third-party tags early | Third parties insight; tag in `<head>` | Load after `load` or on interaction; a facade for chat widgets and video embeds; `<link rel="preconnect">` only for origins used above the fold (at most 2-3) |
| Long tasks in handlers (poor INP) | TBT high; Performance panel shows long tasks; INP from field data | Do the visible update first, then yield: `await scheduler.yield()` when available, else `await new Promise(r => setTimeout(r, 0))`; batch DOM writes; move pure computation to a Web Worker; debounce input handlers |
| Layout thrashing | Reads (`offsetHeight`, `getBoundingClientRect`) between writes in a loop | Read all, then write all; `requestAnimationFrame` for visual updates |

Never defer: scripts the first paint needs, inline configuration read by later scripts, consent managers that must run before trackers, polyfills required by early code.

## CSS and fonts

| Problem | Fix |
|---|---|
| Large render-blocking CSS | Critical CSS inlined by the framework or build (Next.js, Nuxt, Astro, Angular `inlineCritical`); the rest loaded after first paint; unused CSS removed (Tailwind content globs, PurgeCSS) |
| `@import` chains in plain CSS (`css-import`) | Bundle them in the build, or separate `<link>` tags. In Sass and Less, `@import` of partials is inlined at build time and is fine; only `url()`, `.css` and remote targets stay runtime requests |
| Web fonts block text (`font-display`) | `font-display: swap` (or `optional` for non-essential fonts); WOFF2 only; subset; preload at most the one or two fonts used above the fold; self-host where licensing allows |
| Font-swap layout shift | `size-adjust`, `ascent-override` on a fallback `@font-face`, or framework font tools (`next/font`, `@nuxtjs/fontaine`) |
| Long below-the-fold sections | `content-visibility: auto; contain-intrinsic-size: auto 800px;` on section containers (check find-in-page and anchor links still work) |

## Layout stability (CLS)

- Media without dimensions (above); embeds and ads without reserved space (`min-height` from the slot size); banners and consent bars inserted above content (overlay them, or reserve space); content injected above what the user reads after load.
- Animations with `top`/`left`/`width` → `transform` and `opacity`.
- Web fonts (above).

## Network and caching

- HTML: `Cache-Control: no-cache` with an `ETag`; hashed static assets: one year, `immutable`.
- Compression: Brotli or gzip for text assets.
- HTTP/2 or HTTP/3; no domain sharding.
- Back/forward cache: no `unload` handlers, no `Cache-Control: no-store` on pages that don't need it (Lighthouse's bfcache audit).
- Server response (TTFB over about 800 ms) is `perf-review`'s territory; note it and point there.

## Usually fine (don't flag)

- Small images (under about 10 KiB) without `srcset`; decorative CSS backgrounds below the fold.
- `loading="lazy"` absent on images that are above the fold on both mobile and desktop.
- A blocking script that must run first (see "Never defer").
- An extra request that is cached and off the critical path.
