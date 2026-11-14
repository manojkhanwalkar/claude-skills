#!/usr/bin/env python3
"""Find tracking, storage and third-party data flows in a source tree.

Leads for the digital-regulation-check skill (ePrivacy/GDPR consent, DSA ads and
recommenders, DMA data combination, cross-border transfers):

  third-party-script  <script src> or dynamic import from another origin
  tracker             a known analytics/ads/session-replay SDK or endpoint
  cookie-write        code that sets a cookie (document.cookie, Set-Cookie, addCookie, ...)
  client-storage      localStorage / sessionStorage / IndexedDB writes
  fingerprinting      APIs typical of device fingerprinting
  no-sri              a third-party <script src> without an integrity= attribute
  gpc-signal          handling of the Global Privacy Control / Do-Not-Track signal (good)
  consent-check       a consent-management call or gate (good - verify it runs first)

Every hit is a lead: read the code. Prints file:line: kind: detail.

Usage:
  scan_trackers.py [PATH ...]          (default .)
  scan_trackers.py --files-from -      paths from stdin, e.g. git diff --name-only
  scan_trackers.py --json ...

Standard library only. Reads files as data; never executes or imports them.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from typing import Iterator, NamedTuple

MAX_FILE_BYTES = 2 * 1024 * 1024
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "target", "build", "dist", "out",
    ".gradle", ".idea", ".venv", "venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".tox", "coverage", "htmlcov", ".next", "vendor",
}
SCAN_SUFFIXES = (
    ".html", ".htm", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".vue", ".svelte",
    ".java", ".kt", ".py", ".go", ".rb", ".php", ".cs", ".swift", ".m", ".dart",
    ".jsp", ".ftl", ".erb", ".hbs", ".mustache", ".twig", ".jinja", ".j2",
    ".xml", ".gradle", ".kts", ".json", ".yml", ".yaml", ".properties", ".toml",
)

# name -> pattern. Analytics, ads, attribution, session replay, CDPs, social pixels.
TRACKERS = {
    "Google Analytics/Tag Manager": r"google-analytics\.com|googletagmanager\.com|gtag\(|\bga\(\s*['\"](create|send)|firebase/analytics|firebase-analytics",
    "Google Ads/DoubleClick": r"doubleclick\.net|googleadservices\.com|googlesyndication\.com|adservice\.google",
    "Meta Pixel/SDK": r"connect\.facebook\.net|fbq\(|facebook-android-sdk|FBSDKCoreKit|facebook_app_events",
    "LinkedIn Insight": r"snap\.licdn\.com|_linkedin_partner_id",
    "TikTok Pixel": r"analytics\.tiktok\.com|ttq\.(load|track)",
    "X/Twitter pixel": r"static\.ads-twitter\.com|twq\(",
    "Microsoft Clarity/UET": r"clarity\.ms|bat\.bing\.com",
    "Hotjar": r"hotjar\.com|hjid",
    "FullStory": r"fullstory\.com|\bFS\.identify",
    "LogRocket": r"logrocket|LogRocket\.init",
    "Mixpanel": r"mixpanel",
    "Amplitude": r"amplitude\.com|@amplitude/|amplitude\.getInstance",
    "Segment": r"segment\.(com|io)|analytics\.identify\(|@segment/",
    "Heap": r"heapanalytics\.com|heap\.identify",
    "PostHog": r"posthog",
    "Intercom": r"widget\.intercom\.io|Intercom\(\s*['\"]boot",
    "Braze/AppsFlyer/Adjust/Branch": r"braze|appsflyer|adjust\.com|com\.adjust\.sdk|branch\.io",
    "Sentry (may capture PII)": r"sentry\.io|@sentry/|io\.sentry|sentry_sdk",
    "Datadog RUM": r"datadoghq|@datadog/browser-rum",
    "New Relic browser": r"js-agent\.newrelic\.com|nr-data\.net",
}
TRACKER_RES = [(name, re.compile(p, re.IGNORECASE)) for name, p in TRACKERS.items()]

SCRIPT_OPEN = re.compile(r"<script\b", re.IGNORECASE)
SRC_ATTR = re.compile(r"\bsrc\s*=\s*['\"]((?:https?:)?//[^'\"]+)['\"]", re.IGNORECASE)
MAX_TAG_CHARS = 4096
INTEGRITY = re.compile(r"\bintegrity\s*=", re.IGNORECASE)
DYNAMIC_SCRIPT = re.compile(r"createElement\(\s*['\"]script['\"]\s*\)|import\(\s*['\"]https?://")
COOKIE_WRITE = re.compile(
    r"document\.cookie\s*=|set-cookie|\baddCookie\s*\(|\bset_?cookie\s*\(|"
    r"\bres(ponse)?\.cookie\s*\(|cookies(\(\s*\))?\.set\s*\(|ResponseCookie\.from|new\s+Cookie\s*\(|"
    r"HttpCookie\s*\(",
    re.IGNORECASE,
)
CLIENT_STORAGE = re.compile(r"\b(localStorage|sessionStorage)\.setItem\s*\(|\bindexedDB\.open\s*\(")
FINGERPRINT = re.compile(
    r"toDataURL\s*\(|getImageData\s*\(|navigator\.(plugins|hardwareConcurrency|deviceMemory|getBattery)|"
    r"AudioContext|OfflineAudioContext|WEBGL_debug_renderer_info|fingerprintjs|clientjs",
)
GPC = re.compile(r"Sec-GPC|globalPrivacyControl|navigator\.doNotTrack|\bDNT\b", re.IGNORECASE)
CONSENT = re.compile(
    r"__tcfapi|__gpp|OneTrust|Optanon|Cookiebot|CookieConsent|Didomi|Usercentrics|"
    r"iubenda|klaro|consent_?(given|granted|status)|hasConsent|gtag\(\s*['\"]consent",
    re.IGNORECASE,
)
FIRST_PARTY_HOSTS = re.compile(r"//(localhost|127\.0\.0\.1|\[::1\])([:/]|$)")


class Hit(NamedTuple):
    path: str
    line: int
    kind: str
    detail: str


def scan_scripts(path: str, text: str) -> Iterator[Hit]:
    """Third-party <script src> tags, also when the tag spans several lines.

    Finds each "<script" and reads up to the next ">" (bounded), so the cost is
    linear in the file size whatever the markup looks like.
    """
    for m in SCRIPT_OPEN.finditer(text):
        end = text.find(">", m.end(), m.end() + MAX_TAG_CHARS)
        if end < 0:
            continue
        tag = text[m.start():end + 1]
        src = SRC_ATTR.search(tag)
        if not src or FIRST_PARTY_HOSTS.search(src.group(1)):
            continue
        host = src.group(1).split("//", 1)[1].split("/", 1)[0]
        lineno = text.count("\n", 0, m.start()) + 1
        yield Hit(path, lineno, "third-party-script", host)
        if not INTEGRITY.search(tag):
            yield Hit(path, lineno, "no-sri", host)


def scan_line(path: str, lineno: int, line: str) -> Iterator[Hit]:
    """Line-level leads (everything except <script src> tags, see scan_scripts)."""
    if DYNAMIC_SCRIPT.search(line):
        yield Hit(path, lineno, "third-party-script", "dynamic script load")
    for name, rx in TRACKER_RES:
        if rx.search(line):
            yield Hit(path, lineno, "tracker", name)
    m = COOKIE_WRITE.search(line)
    if m:
        yield Hit(path, lineno, "cookie-write", m.group(0).strip())
    m = CLIENT_STORAGE.search(line)
    if m:
        yield Hit(path, lineno, "client-storage", m.group(0).split("(")[0])
    m = FINGERPRINT.search(line)
    if m:
        yield Hit(path, lineno, "fingerprinting", m.group(0).split("(")[0].strip())
    m = GPC.search(line)
    if m:
        yield Hit(path, lineno, "gpc-signal", m.group(0))
    m = CONSENT.search(line)
    if m:
        yield Hit(path, lineno, "consent-check", m.group(0))


def iter_files(roots: list[str]) -> Iterator[str]:
    for root in roots:
        if os.path.isfile(root):
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                yield os.path.join(dirpath, name)


def scan_file(path: str) -> Iterator[Hit]:
    if not path.lower().endswith(SCAN_SUFFIXES) or path.lower().endswith(".min.js"):
        return
    try:
        st = os.lstat(path)
        # Regular files only: no symlinks, FIFOs or devices (a FIFO would block forever).
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE_BYTES:
            return
        with open(path, "rb") as fh:
            data = fh.read(MAX_FILE_BYTES + 1)
    except OSError:
        return
    if len(data) > MAX_FILE_BYTES or b"\0" in data[:8192]:
        return
    yield from scan_text(path, data.decode("utf-8", errors="replace"))


def scan_text(path: str, text: str) -> Iterator[Hit]:
    hits = list(scan_scripts(path, text))
    for lineno, line in enumerate(text.splitlines(), start=1):
        hits.extend(scan_line(path, lineno, line))
    yield from sorted(hits, key=lambda h: h.line)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--files-from", metavar="FILE", help="read paths, one per line ('-' for stdin)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    roots = list(args.paths)
    if args.files_from:
        src = sys.stdin if args.files_from == "-" else open(args.files_from, encoding="utf-8")
        with src:
            roots += [p.strip() for p in src if p.strip()]
    if not roots:
        roots = ["."]
    count = 0
    for path in iter_files(roots):
        for hit in scan_file(path):
            count += 1
            print(json.dumps(hit._asdict()) if args.json else f"{hit.path}:{hit.line}: {hit.kind}: {hit.detail}")
    print(f"# {count} lead(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
