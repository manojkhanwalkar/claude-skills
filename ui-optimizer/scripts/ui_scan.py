#!/usr/bin/env python3
"""Static lead finder for front-end loading problems: heavy images and markup that blocks or shifts.

Every hit is a lead, not a finding: Lighthouse and reading the code decide (an image may be
served through a resizing CDN, a script may be injected late on purpose).

Kinds:
  image-heavy        image file larger than --max-kib (default 200 KiB; SVG uses --max-svg-kib, 50)
  image-dimensions   raster image wider or taller than --max-px (default 2560 px)
  gif-animation      GIF over 100 KiB: a muted looping <video> (MP4/WebM) is usually far smaller
  img-no-size        <img> without both width and height (layout shift, CLS)
  img-loading-unset  <img> with no loading attribute: decide above or below the fold
  lazy-and-high      loading="lazy" together with fetchpriority="high" (contradictory)
  iframe-eager       <iframe> without loading="lazy"
  script-blocking    <script src> without defer, async or type="module" (blocks parsing)
  css-import         @import in a stylesheet (serial, render-blocking request chain)
  font-display       @font-face without font-display
  whole-library      whole-library import of a large package (lodash, moment, rxjs, date-fns
                     namespace, @mui/icons-material, antd) instead of the parts used

Bound attributes count as the attribute (:width, v-bind:width, [width], [attr.width]).
Test files (*.test.*, *.spec.*, test, tests, __tests__, __mocks__ folders) are skipped.

Usage:
  ui_scan.py [PATH ...]            (default .)
  ui_scan.py --files-from -        paths from stdin, e.g. git diff --name-only
  ui_scan.py --json ...

Standard library only. Reads files as data; never executes or imports them.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import struct
import sys
from typing import Iterator, NamedTuple

MAX_FILE_BYTES = 2 * 1024 * 1024
HEADER_BYTES = 256 * 1024
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "target", "build", "dist", "out", ".gradle", ".idea",
    ".venv", "venv", "__pycache__", ".next", ".nuxt", ".svelte-kit", ".output", "coverage", "htmlcov",
    "vendor", "storybook-static", ".lighthouseci",
}
TEST_DIRS = {"test", "tests", "__tests__", "__mocks__"}
TEST_FILE = re.compile(r"\.(?:test|spec)\.[a-z]+$", re.IGNORECASE)
RASTER = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif")
MARKUP = (".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro", ".jsp", ".ftl", ".erb", ".hbs",
          ".mustache", ".twig", ".jinja", ".j2", ".cshtml", ".razor", ".php")
SCRIPT = (".js", ".mjs", ".ts", ".jsx", ".tsx", ".vue", ".svelte")
STYLE = (".css", ".scss", ".sass", ".less")

TAG = re.compile(r"""<(img|iframe|script)\b((?:"[^"]*"|'[^']*'|\{[^}]*\}|[^>"'{])*)>""", re.IGNORECASE | re.DOTALL)
COMPONENT_FILES = (".jsx", ".tsx", ".vue", ".svelte", ".astro")
ATTR = re.compile(r"""(?:^|\s)(?:v-bind:|v-on:|:|@|#|\*|\(|\[\(?(?:attr\.)?)?([a-zA-Z_][\w.-]*)\)?\]?\s*(?:=\s*("[^"]*"|'[^']*'|\{[^}]*\}|[^\s>]+))?""")
CSS_IMPORT = re.compile(r"^\s*@import\s", re.MULTILINE)
# Sass and Less inline @import at build time; only url(), .css and remote targets stay runtime requests.
PRE_IMPORT = re.compile(r"""^\s*@import\s+(?:url\(|["'][^"']*\.css["']|["']https?:)""", re.MULTILINE)
FONT_FACE = re.compile(r"@font-face\s*\{([^}]*)\}", re.IGNORECASE)
WHOLE_LIB = re.compile(
    r"""^\s*import\s+(?:\*\s+as\s+\w+|\w+)\s+from\s+['"](lodash|moment|rxjs|date-fns|@mui/icons-material|antd)['"]"""
    r"""|require\(\s*['"](lodash|moment)['"]\s*\)""", re.MULTILINE)


class Hit(NamedTuple):
    path: str
    line: int
    kind: str
    detail: str


def is_test(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    return bool(TEST_FILE.search(parts[-1])) or any(p in TEST_DIRS for p in parts[:-1])


def attrs(text: str) -> dict:
    found = {}
    for m in ATTR.finditer(text):
        raw = m.group(2) or ""
        value = raw.strip("\"'{}").strip() if raw[:1] in "\"'{" else raw.rstrip("/")
        found[m.group(1).lower()] = value.lower()
    return found


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def scan_markup(path: str, text: str) -> list[Hit]:
    hits = []
    components = path.lower().endswith(COMPONENT_FILES)
    for m in TAG.finditer(text):
        if components and m.group(1)[0].isupper():
            continue  # a framework component such as next/script <Script> or <Img>, not the HTML tag
        name, a = m.group(1).lower(), attrs(m.group(2))
        line = line_of(text, m.start())
        if name == "img":
            if "width" not in a or "height" not in a:
                hits.append(Hit(path, line, "img-no-size", "add width and height (or aspect-ratio) to reserve space"))
            if "loading" not in a:
                hits.append(Hit(path, line, "img-loading-unset", "above the fold: eager (LCP: fetchpriority=high); below: loading=lazy"))
            if a.get("loading") == "lazy" and a.get("fetchpriority") == "high":
                hits.append(Hit(path, line, "lazy-and-high", "an image can't be both lazy and high priority"))
        elif name == "iframe" and a.get("loading") != "lazy":
            hits.append(Hit(path, line, "iframe-eager", "add loading=lazy, or a click-to-load facade"))
        elif name == "script" and "src" in a and not ({"defer", "async"} & a.keys()) and a.get("type") != "module":
            hits.append(Hit(path, line, "script-blocking", f"src={a['src'][:80]}: add defer (order kept) or async"))
    return hits


def scan_style(path: str, text: str) -> list[Hit]:
    pattern = PRE_IMPORT if path.lower().endswith((".scss", ".sass", ".less")) else CSS_IMPORT
    hits = [Hit(path, line_of(text, m.start()), "css-import", "inline it in the build or use <link>")
            for m in pattern.finditer(text)]
    for m in FONT_FACE.finditer(text):
        if "font-display" not in m.group(1).lower():
            hits.append(Hit(path, line_of(text, m.start()), "font-display", "add font-display: swap (or optional)"))
    return hits


def scan_script(path: str, text: str) -> list[Hit]:
    return [Hit(path, line_of(text, m.start()), "whole-library",
                f"import only what is used from {m.group(1) or m.group(2)}")
            for m in WHOLE_LIB.finditer(text)]


def scan_text(path: str, text: str) -> list[Hit]:
    lower = path.lower()
    hits: list[Hit] = []
    if lower.endswith(MARKUP):
        hits += scan_markup(path, text)
    if lower.endswith(STYLE):
        hits += scan_style(path, text)
    if lower.endswith((".html", ".htm", ".vue", ".svelte", ".astro")):
        hits += [h for h in scan_style(path, text) if h.kind == "font-display"]
    if lower.endswith(SCRIPT):
        hits += scan_script(path, text)
    return hits


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
            i += 1 if marker == 0xFF else 2
            continue
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + length
    return None


def image_size(data: bytes) -> tuple[int, int] | None:
    """Pixel width and height from the file header, or None when the format or file is unknown."""
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return struct.unpack("<HH", data[6:10])
    if data.startswith(b"\xff\xd8"):
        return _jpeg_size(data)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and len(data) >= 30:
        chunk = data[12:16]
        if chunk == b"VP8X":
            return (int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1)
        if chunk == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
        if chunk == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return (w & 0x3FFF, h & 0x3FFF)
    i = data.find(b"ispe")
    if b"ftypavif" in data[:32] and i >= 0 and len(data) >= i + 16:
        return struct.unpack(">II", data[i + 8:i + 16])
    return None


def scan_image(path: str, size: int, head: bytes, max_kib: int, max_svg_kib: int, max_px: int) -> list[Hit]:
    lower, kib = path.lower(), size / 1024
    hits = []
    limit = max_svg_kib if lower.endswith(".svg") else max_kib
    if kib > limit:
        hits.append(Hit(path, 0, "image-heavy", f"{kib:.0f} KiB (limit {limit}): resize, AVIF/WebP, compress"))
    if lower.endswith(".gif") and kib > 100:
        hits.append(Hit(path, 0, "gif-animation", f"{kib:.0f} KiB GIF: use a muted looping <video>"))
    if lower.endswith(RASTER):
        dims = image_size(head)
        if dims and max(dims) > max_px:
            hits.append(Hit(path, 0, "image-dimensions", f"{dims[0]}x{dims[1]} px (limit {max_px}): serve srcset sizes"))
    return hits


def walk(paths: list[str]) -> Iterator[str]:
    for root in paths:
        if os.path.isfile(root):
            yield root
            continue
        for d, dirs, files in os.walk(root):
            dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
            for f in sorted(files):
                yield os.path.join(d, f)


def scan_paths(paths: list[str], max_kib: int = 200, max_svg_kib: int = 50, max_px: int = 2560) -> list[Hit]:
    hits: list[Hit] = []
    for path in walk(paths):
        rel = os.path.relpath(path)
        if is_test(rel):
            continue
        try:
            st = os.stat(path)
        except OSError:
            continue
        if not stat.S_ISREG(st.st_mode):
            continue
        lower = rel.lower()
        if lower.endswith(RASTER + (".svg",)):
            with open(path, "rb") as fh:
                hits += scan_image(rel, st.st_size, fh.read(HEADER_BYTES), max_kib, max_svg_kib, max_px)
        elif lower.endswith(MARKUP + SCRIPT + STYLE) and st.st_size <= MAX_FILE_BYTES:
            with open(path, encoding="utf-8", errors="replace") as fh:
                hits += scan_text(rel, fh.read())
    return hits


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("paths", nargs="*")
    p.add_argument("--files-from", help="read paths from this file, '-' for stdin")
    p.add_argument("--json", action="store_true")
    p.add_argument("--max-kib", type=int, default=200)
    p.add_argument("--max-svg-kib", type=int, default=50)
    p.add_argument("--max-px", type=int, default=2560)
    args = p.parse_args(argv)
    paths = list(args.paths)
    if args.files_from:
        stream = sys.stdin if args.files_from == "-" else open(args.files_from, encoding="utf-8")
        with stream:
            paths += [line.strip() for line in stream if line.strip()]
        paths = [x for x in paths if os.path.exists(x)]
        if not paths:
            print("ui_scan: no existing files to scan")
            return 0
    hits = scan_paths(paths or ["."], args.max_kib, args.max_svg_kib, args.max_px)
    if args.json:
        print(json.dumps([h._asdict() for h in hits], indent=2))
    else:
        for h in hits:
            print(f"{h.path}:{h.line}: {h.kind}: {h.detail}")
        counts: dict[str, int] = {}
        for h in hits:
            counts[h.kind] = counts.get(h.kind, 0) + 1
        print("ui_scan: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "no leads"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
