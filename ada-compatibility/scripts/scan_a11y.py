#!/usr/bin/env python3
"""Static lead finder for common accessibility (ADA / WCAG 2.2 AA) defects in UI source.

Scans HTML, templates, JSX/TSX, Vue/Svelte and CSS. Every hit is a lead: read the code
(a label may be added by script, a name may come from aria-labelledby elsewhere).

Kinds (WCAG success criterion in brackets):
  img-alt            <img> without an alt attribute                         [1.1.1]
  input-label        form control with no id-linked <label>, aria-label(ledby),
                     title, or wrapping <label>                             [1.3.1, 3.3.2, 4.1.2]
  button-name        <button> / role=button with no text and no aria-label  [4.1.2]
  link-name          <a href> with no text and no aria-label                [2.4.4, 4.1.2]
  html-lang          <html> without lang                                    [3.1.1]
  page-title         a full HTML page without a non-empty <title>           [2.4.2]
  positive-tabindex  tabindex greater than 0                                [2.4.3]
  click-no-key       onClick/@click/(click) on div/span/li/td/img without a role
                     and tabindex (not keyboard operable)                   [2.1.1, 4.1.2]
  anchor-no-href     <a> used as a button (no href, or href="#"/"javascript:") [2.1.1, 4.1.2]
  aria-hidden-focus  aria-hidden="true" on a focusable element              [4.1.2]
  no-zoom            viewport meta that blocks zoom (user-scalable=no, maximum-scale<2) [1.4.4]
  outline-none       outline: none/0 in CSS (check a visible :focus-visible style exists) [2.4.7]
  autoplay           <video>/<audio> with autoplay                         [1.4.2, 2.2.2]
  heading-skip       heading level jumps by more than one (h2 -> h4) in a file [1.3.1]
  paste-blocked      onpaste that prevents paste (blocks password managers) [3.3.8]

Usage:
  scan_a11y.py [PATH ...]           (default .)
  scan_a11y.py --files-from -       paths from stdin, e.g. git diff --name-only
  scan_a11y.py --json ...

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
MAX_TAG_CHARS = 4096
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "target", "build", "dist", "out", ".gradle", ".idea",
    ".venv", "venv", "__pycache__", ".next", ".nuxt", "coverage", "htmlcov", "vendor", "storybook-static",
}
MARKUP_SUFFIXES = (".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".jsp", ".ftl", ".erb", ".hbs",
                   ".mustache", ".twig", ".jinja", ".j2", ".cshtml", ".razor", ".php", ".astro")
SCRIPT_SUFFIXES = (".js", ".mjs", ".ts")  # may build markup in template literals
STYLE_SUFFIXES = (".css", ".scss", ".sass", ".less")

TAG_OPEN = re.compile(r"<([a-zA-Z][a-zA-Z0-9-]*)\b")
# Attribute keys include Vue (:x, @x, v-bind:x), Svelte (on:x) and Angular ([x], (x), [attr.x]) bindings.
ATTR = re.compile(r"""(\[[\w.:-]+\]|\([\w.:-]+\)|[:@#*a-zA-Z_][-:.\w]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|\{([^{}]*)\}|([^\s"'>]+)))?""")
LABEL_FOR = re.compile(r"""<label\b[^>]{0,500}?\s(?:(?::|v-bind:)?for|htmlFor|\[for\]|\[attr\.for\])\s*=\s*(?:["'{]\s*["']?)?([^"'}\s>]+)""",
                       re.IGNORECASE)
TITLE = re.compile(r"<title\b[^>]{0,200}>\s*([^<\s][^<]*)</title>", re.IGNORECASE)
HEADING = re.compile(r"<h([1-6])\b", re.IGNORECASE)
NONE_VALUE = r"\s*(?:none|0(?:px|em|rem)?)\s*(?:!important\s*)?[;}]"
OUTLINE_NONE = re.compile(r"outline\s*:\s*(?:none|0(?:px|em|rem)?)(?![\w.])", re.IGNORECASE)
# A replacement focus indicator: a visible outline, box-shadow or border on a :focus rule (not "none"/0).
FOCUS_STYLE = re.compile(r":focus(?:-visible|-within)?\b[^{]{0,500}\{[^}]{0,2000}?"
                         r"(?:outline|box-shadow|border(?:-[a-z]+)?)\s*:(?!" + NONE_VALUE + r")", re.IGNORECASE)
PASTE_BLOCK = re.compile(r"""on[Pp]aste\s*=\s*["'{][^"'}]*(return\s+false|preventDefault)""")

FORM_CONTROLS = {"input", "select", "textarea"}
NO_LABEL_INPUT_TYPES = {"hidden", "submit", "reset", "button", "image"}
CLICK_ATTRS = {"onclick", "@click", "v-on:click", "(click)", "on:click"}
NON_INTERACTIVE = {"div", "span", "li", "td", "tr", "img", "p", "section", "article", "svg"}
NATIVELY_FOCUSABLE = {"a", "button", "input", "select", "textarea", "summary", "iframe"}


class Hit(NamedTuple):
    path: str
    line: int
    kind: str
    detail: str


class Tag(NamedTuple):
    name: str
    attrs: dict
    start: int
    end: int          # index just after '>'
    self_closing: bool


def parse_tags(text: str, jsx: bool = False) -> Iterator[Tag]:
    """Opening tags with attributes, in one left-to-right pass.

    Each tag is read up to the next '>' within MAX_TAG_CHARS. In JSX, a '>' inside {...} doesn't end
    the tag, so braces are balanced incrementally. The next search starts after the tag, so no text is
    read twice and the cost stays linear in the file size.
    """
    pos = 0
    while True:
        m = TAG_OPEN.search(text, pos)
        if not m:
            return
        name = m.group(1)
        limit = m.end() + MAX_TAG_CHARS
        stop = text.find(">", m.end(), limit)
        if stop < 0:
            pos = m.end()
            continue
        if jsx:
            balance = text.count("{", m.end(), stop) - text.count("}", m.end(), stop)
            while balance > 0:
                nxt = text.find(">", stop + 1, limit)
                if nxt < 0:
                    break
                balance += text.count("{", stop + 1, nxt) - text.count("}", stop + 1, nxt)
                stop = nxt
        pos = stop + 1
        body = text[m.end():stop]
        attrs = {}
        for a in ATTR.finditer(body):
            key = normalise_key(a.group(1))
            value = next((g for g in a.groups()[1:] if g is not None), None)
            attrs[key] = value if value is not None else ""
        yield Tag(name, attrs, m.start(), stop + 1, body.rstrip().endswith("/"))


def normalise_key(key: str) -> str:
    """Bound attributes count as the attribute: [attr.aria-label] / [aria-label] -> aria-label. (click) stays."""
    key = key.lower()
    if key.startswith("[") and key.endswith("]"):
        key = key[1:-1]
        if key.startswith("attr."):
            key = key[5:]
    return key


def blank_comments(text: str) -> str:
    """HTML comments replaced by spaces (newlines kept, so line numbers stay right); linear."""
    out, pos = [], 0
    while True:
        start = text.find("<!--", pos)
        if start < 0:
            out.append(text[pos:])
            return "".join(out)
        end = text.find("-->", start + 4)
        end = len(text) if end < 0 else end + 3
        out.append(text[pos:start])
        out.append("".join(c if c == "\n" else " " for c in text[start:end]))
        pos = end


def inner_text(text: str, tag: Tag, limit: int = 2000) -> str | None:
    """Content up to the matching close tag (same name, not nested-aware beyond depth counting)."""
    if tag.self_closing:
        return ""
    name = re.escape(tag.name)
    depth, pos = 1, tag.end
    pattern = re.compile(rf"<(/?){name}\b[^>]*>", re.IGNORECASE)
    end_limit = min(len(text), tag.end + limit)
    while depth:
        m = pattern.search(text, pos, end_limit)
        if not m:
            return None  # unknown (too long or unclosed): don't guess
        depth += -1 if m.group(1) else 1
        pos = m.end()
        if depth == 0:
            return text[tag.end:m.start()]
    return None


def visible_text(fragment: str) -> str:
    """Text content: tags removed, but img alt text and aria-label values count as names."""
    alts = " ".join(re.findall(r"""\b(?:alt|aria-label)\s*=\s*["']([^"']+)["']""", fragment))
    stripped = re.sub(r"<[^>]*>", " ", fragment)
    return (stripped + " " + alts).strip()


NAME_ATTRS = ("aria-label", "aria-labelledby", "title")


def has_name(attrs: dict) -> bool:
    for key in NAME_ATTRS:
        for variant in (key, ":" + key, "v-bind:" + key):
            if attrs.get(variant, "").strip():
                return True
    return False


class Lines:
    """Line numbers by binary search over newline offsets, so a big file stays linear-ish."""

    def __init__(self, text: str):
        self.starts = [i for i, c in enumerate(text) if c == "\n"]

    def of(self, index: int) -> int:
        import bisect
        return bisect.bisect_left(self.starts, index) + 1


def scan_markup(path: str, text: str) -> Iterator[Hit]:
    import bisect
    text = blank_comments(text)
    lower_path = path.lower()
    jsx = lower_path.endswith((".jsx", ".tsx", ".js", ".mjs", ".ts", ".astro"))
    # Outside plain HTML, a capitalised tag is a component (<Button label=…>), not the HTML element.
    components_capitalised = not lower_path.endswith((".html", ".htm"))
    labelled_ids = {m.group(1) for m in LABEL_FOR.finditer(text)}
    tags = list(parse_tags(text, jsx))
    label_spans = []
    for tag in tags:
        if tag.name.lower() == "label":
            content = inner_text(text, tag, 4000)
            if content is not None:
                label_spans.append((tag.end, tag.end + len(content)))
    label_spans.sort()
    label_starts = [start for start, _ in label_spans]

    def inside_a_label(index: int) -> bool:
        i = bisect.bisect_right(label_starts, index) - 1
        return i >= 0 and label_spans[i][0] <= index < label_spans[i][1]
    full_page = re.search(r"<html\b", text, re.IGNORECASE) is not None
    lines = Lines(text)
    last_heading = 0

    for tag in tags:
        if components_capitalised and tag.name[0].isupper():
            continue
        name = tag.name.lower()
        a = tag.attrs
        ln = lines.of(tag.start)
        role = a.get("role", "").lower()

        if name == "html" and "lang" not in a and ":lang" not in a:
            yield Hit(path, ln, "html-lang", "<html> has no lang")

        if name == "img" and "alt" not in a and ":alt" not in a and "aria-hidden" not in a \
                and role not in {"presentation", "none"}:
            yield Hit(path, ln, "img-alt", "<img> without alt (use alt=\"\" if decorative)")

        if name in FORM_CONTROLS:
            kind = a.get("type", "text").lower()
            if not (name == "input" and kind in NO_LABEL_INPUT_TYPES):
                control_id = a.get("id") or a.get(":id") or a.get("v-bind:id") or ""
                inside_label = inside_a_label(tag.start)
                if not (has_name(a) or (control_id and control_id in labelled_ids) or inside_label):
                    yield Hit(path, ln, "input-label", f"<{name}{' type=' + kind if name == 'input' else ''}> has no label")

        if name == "button" or role == "button":
            content = inner_text(text, tag)
            if content is not None and not visible_text(content) and not has_name(a) and "value" not in a:
                yield Hit(path, ln, "button-name", f"<{tag.name}> has no accessible name")

        if name == "a":
            href = a.get("href")
            if href is None and "to" not in a and ":href" not in a and "routerlink" not in a:
                if any(k in a for k in CLICK_ATTRS) and role != "button":
                    yield Hit(path, ln, "anchor-no-href", "<a> without href used as a button")
            elif href is not None and (href.strip() in {"#", ""} or href.strip().lower().startswith("javascript:")):
                yield Hit(path, ln, "anchor-no-href", f"<a href=\"{href.strip()[:20]}\"> used as a button")
            if href is not None or "to" in a:
                content = inner_text(text, tag)
                if content is not None and not visible_text(content) and not has_name(a):
                    yield Hit(path, ln, "link-name", "link has no accessible name")

        tabindex = a.get("tabindex", "")
        if re.fullmatch(r"\s*[1-9]\d*\s*", tabindex):
            yield Hit(path, ln, "positive-tabindex", f"tabindex={tabindex.strip()}")

        if name in NON_INTERACTIVE and any(k in a for k in CLICK_ATTRS):
            if not role or "tabindex" not in a:
                yield Hit(path, ln, "click-no-key", f"<{name}> with a click handler but no role/tabindex")

        if a.get("aria-hidden", "").lower() == "true" and (name in NATIVELY_FOCUSABLE or "tabindex" in a) \
                and a.get("tabindex", "").strip() != "-1":
            yield Hit(path, ln, "aria-hidden-focus", f"aria-hidden on focusable <{name}>")

        if name == "meta" and a.get("name", "").lower() == "viewport":
            content = a.get("content", "").lower().replace(" ", "")
            scale = re.search(r"maximum-scale=(\d+(?:\.\d+)?)", content)
            if "user-scalable=no" in content or "user-scalable=0" in content or (scale and float(scale.group(1)) < 2):
                yield Hit(path, ln, "no-zoom", "viewport blocks zoom")

        if name in {"video", "audio"} and "autoplay" in a:
            yield Hit(path, ln, "autoplay", f"<{name} autoplay>")

        m = re.fullmatch(r"h([1-6])", name)
        if m:
            level = int(m.group(1))
            if last_heading and level > last_heading + 1:
                yield Hit(path, ln, "heading-skip", f"h{last_heading} -> h{level}")
            last_heading = level

    if full_page and not TITLE.search(text):
        yield Hit(path, 1, "page-title", "page has no non-empty <title>")
    for m in PASTE_BLOCK.finditer(text):
        yield Hit(path, lines.of(m.start()), "paste-blocked", "paste is prevented")


def scan_style(path: str, text: str) -> Iterator[Hit]:
    if FOCUS_STYLE.search(text):
        return  # a replacement focus style exists in this file; still verify it applies
    lines = Lines(text)
    for m in OUTLINE_NONE.finditer(text):
        yield Hit(path, lines.of(m.start()), "outline-none", "outline removed with no focus style in this file")


def scan_text(path: str, text: str) -> list[Hit]:
    lower = path.lower()
    hits: list[Hit] = []
    if lower.endswith(STYLE_SUFFIXES):
        hits.extend(scan_style(path, text))
    elif lower.endswith(MARKUP_SUFFIXES) or (lower.endswith(SCRIPT_SUFFIXES) and "<" in text):
        hits.extend(scan_markup(path, text))
        if lower.endswith((".html", ".htm", ".vue", ".svelte")):
            lowered = text.lower()
            pos = 0
            while (start := lowered.find("<style", pos)) >= 0:
                open_end = lowered.find(">", start)
                close = lowered.find("</style", open_end + 1) if open_end >= 0 else -1
                if close < 0:
                    break
                body = text[open_end + 1:close]
                offset = text.count("\n", 0, open_end + 1)
                hits.extend(h._replace(line=h.line + offset) for h in scan_style(path, body))
                pos = close + 7
    return sorted(hits, key=lambda h: h.line)


def iter_files(roots: list[str]) -> Iterator[str]:
    for root in roots:
        if os.path.isfile(root):
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                yield os.path.join(dirpath, name)


def scan_file(path: str) -> list[Hit]:
    if not path.lower().endswith(MARKUP_SUFFIXES + SCRIPT_SUFFIXES + STYLE_SUFFIXES) or path.lower().endswith(".min.js"):
        return []
    try:
        st = os.lstat(path)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE_BYTES:
            return []
        with open(path, "rb") as fh:
            data = fh.read(MAX_FILE_BYTES + 1)
    except OSError:
        return []
    if len(data) > MAX_FILE_BYTES or b"\0" in data[:8192]:
        return []
    return scan_text(path, data.decode("utf-8", errors="replace"))


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
