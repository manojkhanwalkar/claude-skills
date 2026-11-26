# Framework idioms

Use the framework's own tool before hand-written markup or new dependencies.

| Framework | Images | Lazy code and hydration | Fonts and CSS |
|---|---|---|---|
| Next.js (App Router) | `next/image`: `width`/`height` or `fill` + `sizes`; `priority` (or `preload` in newer versions) only on the LCP image; others lazy by default; AVIF via `images.formats` | Server Components by default; `next/dynamic` (with `ssr: false` only for browser-only widgets); `next/script` `strategy="lazyOnload"` or `afterInteractive` for third parties | `next/font` (self-hosted, size-adjusted fallbacks); CSS Modules or Tailwind |
| Nuxt 3/4 | `@nuxt/image` `<NuxtImg>`/`<NuxtPicture>` with `sizes`, `format="avif,webp"`, `loading`, `fetchpriority`, `preload` | `Lazy` prefix on components (`<LazyFooChart>`), lazy hydration (`hydrate-on-visible`, `hydrate-on-idle`), `useScript` with a trigger for third parties | `@nuxt/fonts`, `@nuxtjs/fontaine` |
| Angular 17+ | `NgOptimizedImage` (`ngSrc`, `width`, `height`, `priority` on the LCP image, `ngSrcset`, image loaders for CDNs) | `@defer (on viewport / idle / interaction)` blocks, lazy routes (`loadComponent`), incremental hydration (`withIncrementalHydration`) | `inlineCritical` and font inlining in the build optimization config |
| Vite + React | `<img>` with `srcset`/`sizes`, `loading`, `fetchpriority` (React 19 passes `fetchPriority`); `vite-imagetools` only if already used | `React.lazy` + `Suspense`, route-level splitting (React Router `lazy`), `startTransition` for non-urgent updates | `build.target` to modern browsers; CSS code splitting is on by default |
| Vite + Vue | `<img>` attributes as above | `defineAsyncComponent`, lazy routes (`component: () => import(...)`) | as Vite + React |
| SvelteKit | `@sveltejs/enhanced-img` `<enhanced:img>` (AVIF/WebP, dimensions) | Dynamic `import()` in components; `data-sveltekit-preload-data` tuning | Inline small CSS (`inlineStyleThreshold`) |
| Astro | `<Image>` and `<Picture>` from `astro:assets` (formats, dimensions, lazy by default) | Islands: `client:visible`, `client:idle`, `client:media`; ship zero JS by default | Fonts API or self-hosted fonts |
| Server templates (Thymeleaf, JSP, Jinja, ERB, Razor) | Plain `<img>`/`<picture>` attributes; resize at build time or through a CDN image service | `defer`/`async` on scripts, `type="module"`, load widgets on interaction | `<link rel="preload">` for one or two fonts; no `@import` |

Static hosting and CDNs (CloudFront, Cloudflare, Fastly, Netlify, Vercel) often resize and convert images on the fly; prefer that to committing many variants, and check cache headers on the transformed URLs.
