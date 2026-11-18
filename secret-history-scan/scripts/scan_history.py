"""Scan a git repository's whole history for committed secrets (stdlib only; git 2.31+).

Usage:
    python3 -I scan_history.py <repo> [--reflog] [--allow <file>] [--key-file <file>] [--out <file.json>]
    python3 -I scan_history.py <repo> --context <commit>:<path>:<line> [--radius <n>]

Reads every commit reachable from any ref (and the reflog with --reflog), including what merge
commits add relative to their first parent, and checks the lines each commit added. Binary files
are not scanned. A secret's value is never printed or written: a finding carries a masked form
and a keyed fingerprint (HMAC-SHA256 with a local key), which is what an allow-list file lists,
one per line, with '#' comments. Fingerprints are only comparable on machines that share the key.

--context prints the lines around one finding with every recognised secret masked, so a finding
can be triaged without showing its value.

Exit status: 0 no findings, 1 findings, 2 usage, I/O or git error.
"""

import argparse
import codecs
import hashlib
import hmac
import json
import math
import os
import re
import secrets as token_source
import subprocess
import sys
from collections import Counter
from pathlib import Path

# Well-known token formats: (rule id, pattern). The first group holds the secret.
RULES = [
    ("aws-access-key-id", re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b")),
    ("github-token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{36,})\b")),
    ("github-fine-grained-pat", re.compile(r"\b(github_pat_[A-Za-z0-9_]{50,})\b")),
    ("anthropic-api-key", re.compile(r"\b(sk-ant-[A-Za-z0-9_\-]{20,})")),
    ("openai-api-key", re.compile(r"\b(sk-(?:proj-)?[A-Za-z0-9_\-]{32,})")),
    ("slack-token", re.compile(r"\b(xox[abposr]-[A-Za-z0-9-]{10,})\b")),
    ("google-api-key", re.compile(r"\b(AIza[0-9A-Za-z_\-]{35})\b")),
    ("stripe-live-key", re.compile(r"\b((?:sk|rk)_live_[0-9A-Za-z]{24,})\b")),
    ("jwt", re.compile(r"\b(eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b")),
]
KEY_BEGIN = re.compile(r"-----BEGIN ((?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?)-----")
KEY_END = re.compile(r"-----END ((?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?)-----")
KEY_MAX_LINES = 200

# "<something>password<something> = value" in code, JSON, YAML or .env form.
GENERIC = re.compile(
    r"(?i)([\w.-]*(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?key|auth[_-]?token|token)[\w.-]*)"
    r"[\"']?\s*[:=]\s*([\"']?)([^'\"\s,;]{12,})"
)
NOT_A_SECRET_NAME = re.compile(r"(?i)tokens|tokenizer|token_?(?:type|count|limit|url|endpoint|file|path)")
CODE_LIKE = re.compile(r"\(|^[A-Za-z_]\w*\.[A-Za-z_]")  # a call, or self.x / os.environ / process.env
URL_PASSWORD = re.compile(r"(://[^:/\s@]+:)([^@\s/]+)(@)")
RANDOM_LOOKING = re.compile(r"[A-Za-z0-9_+/=\-]{12,}")
# Key material: a base64 line, a PEM header field, or a blank line inside the block. Lines kept
# in a block are still scanned for other secrets, so a bare token after a stray header is found.
BASE64_BODY = re.compile(r"^\s*(?:[A-Za-z0-9+/=]+|(?:Proc-Type|DEK-Info|Version|Comment): .*)?\s*$")
# For the --context view: any assignment to a secret-ish name, whatever the value's length.
CONTEXT_ASSIGN = re.compile(
    r"(?i)([\w.-]*(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?key|auth[_-]?token|token)[\w.-]*"
    r"[\"']?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
QUOTED = re.compile(r"(\"[^\"]{6,}\"|'[^']{6,}')")
GENERIC_MIN_ENTROPY = 3.5
PLACEHOLDER = re.compile(r"(?i)(example|placeholder|changeme|dummy|xxxx|your[_-]|<|\$\{|\{\{|\$\(|%\()")
SHORT = 20  # values shorter than this get no visible prefix
HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class ScanError(Exception):
    pass


def entropy(value: str) -> float:
    """Shannon entropy in bits per character."""
    counts = Counter(value)
    return -sum(n / len(value) * math.log2(n / len(value)) for n in counts.values())


def fingerprint(value: str, key: bytes) -> str:
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()[:24]


def mask(rule: str, value: str) -> str:
    if rule == "private-key":
        label = KEY_BEGIN.search(value)
        return f"[{label.group(1) if label else 'PRIVATE KEY'} block, {len(value)} chars]"
    if rule == "generic-secret-assignment" or len(value) < SHORT:
        return f"…({len(value)} chars)"
    return f"{value[:4]}…({len(value)} chars)"


def find_in_line(line: str):
    """Yield (rule, value) for each single-line secret on a line."""
    seen = set()
    for rule, pattern in RULES:
        for match in pattern.finditer(line):
            value = match.group(1)
            if value not in seen:  # an Anthropic key also matches the OpenAI shape
                seen.add(value)
                yield rule, value
    for match in GENERIC.finditer(line):
        name, quote, value = match.group(1), match.group(2), match.group(3)
        if value in seen or PLACEHOLDER.search(value) or entropy(value) < GENERIC_MIN_ENTROPY:
            continue
        if NOT_A_SECRET_NAME.search(name) or (not quote and CODE_LIKE.search(value)):
            continue
        if any(pattern.search(value) for _, pattern in RULES):
            continue
        seen.add(value)
        yield "generic-secret-assignment", value


def unquote_path(raw: str) -> str:
    """Path from a '+++ ' header: strip git's trailing tab, C-unquote, drop the 'b/' prefix."""
    raw = raw[:-1] if raw.endswith("\t") else raw
    if raw.startswith('"') and raw.endswith('"'):
        try:
            raw = codecs.escape_decode(raw[1:-1].encode("utf-8"))[0].decode("utf-8", "replace")
        except (ValueError, UnicodeError):
            raw = raw[1:-1]  # keep scanning; the path is only a label here
    return raw[2:] if raw.startswith("b/") else raw


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                              errors="replace", check=False)
    except OSError as error:
        raise ScanError(f"cannot run git: {error}") from error


def added_lines(repo: Path, reflog: bool):
    """Yield (commit, date, path, line number, hunk id, text) for every added line, oldest first.

    Parses the diff with a state machine, so an added line that looks like a header can't
    change the current file, and quoted paths are decoded.
    """
    args = ["-c", "core.quotePath=false", "log", "--all", "--topo-order", "--reverse", "-p",
            "--diff-merges=first-parent", "--no-color", "--no-ext-diff", "--no-renames",
            "--unified=0", "--format=COMMIT %H %cI"]
    if reflog:
        args.insert(4, "--reflog")
    try:
        proc = subprocess.Popen(["git", "-C", str(repo), *args], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, errors="replace")
    except OSError as error:
        raise ScanError(f"cannot run git: {error}") from error
    commit = date = path = None
    new_left = old_left = 0
    lineno = hunk = 0
    in_header = False
    with proc:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\n").rstrip("\r")
            if new_left or old_left:  # inside a hunk: only +, - and \ lines
                if line.startswith("+"):
                    new_left -= 1
                    yield commit, date, path, lineno, hunk, line[1:]
                    lineno += 1
                elif line.startswith("-"):
                    old_left -= 1
                continue
            if line.startswith("COMMIT "):
                _, commit, date = line.split(" ", 2)
                path, in_header = None, False
            elif line.startswith("diff --git ") or line.startswith("diff --cc "):
                path, in_header = None, True
            elif in_header and line.startswith("+++ "):
                target = line[4:]
                path = None if target == "/dev/null" else unquote_path(target)
                in_header = False
            elif not in_header and path is not None and (match := HUNK.match(line)):
                old_left = int(match.group(1)) if match.group(1) is not None else 1
                lineno = int(match.group(2))
                new_left = int(match.group(3)) if match.group(3) is not None else 1
                hunk += 1
    if proc.returncode != 0:
        raise ScanError("git log failed")


def in_head(repo: Path, path: str, value: str) -> bool:
    shown = git(repo, "show", f"HEAD:{path}")
    return shown.returncode == 0 and value in shown.stdout


def scan(repo: Path, key: bytes, reflog: bool = False, allowed: frozenset = frozenset()) -> list:
    findings: dict = {}

    def record(rule, value, commit, date, path, lineno):
        fp = fingerprint(value, key)
        if fp in allowed:
            return
        entry = findings.get(fp)
        if entry is None:  # history runs oldest first, so the first sighting introduced it
            entry = findings[fp] = {"rule": rule, "masked": mask(rule, value), "fingerprint": fp,
                                    "first_commit": commit, "first_date": date, "line": lineno,
                                    "paths": [], "_value": value}
        if path not in entry["paths"]:
            entry["paths"].append(path)

    key_block = None  # (hunk, commit, date, path, start line, lines)

    def close_block():
        nonlocal key_block
        _, commit, date, path, lineno, lines = key_block
        value = "\n".join(lines)
        if len(lines) == 1:  # a header with no key body: make it unique to its place
            value += f"\n@{commit}:{path}:{lineno}"
        record("private-key", value, commit, date, path, lineno)
        key_block = None

    for commit, date, path, lineno, hunk, text in added_lines(repo, reflog):
        if key_block and (key_block[0] != hunk or not (KEY_END.search(text) or BASE64_BODY.match(text))):
            close_block()  # the hunk ended, or this line isn't key material: scan it normally
        if key_block:
            key_block[5].append(text)
            for rule, value in find_in_line(text):  # key lines are scanned too, in case
                record(rule, value, commit, date, path, lineno)
            if KEY_END.search(text) or len(key_block[5]) >= KEY_MAX_LINES:
                close_block()
            continue
        rest = text
        begin = KEY_BEGIN.search(text)
        if begin:
            end = KEY_END.search(text, begin.end())
            if end:  # the whole key on one line (for example JSON with escaped newlines)
                record("private-key", text[begin.start():end.end()], commit, date, path, lineno)
                rest = text[:begin.start()] + " " + text[end.end():]
            else:
                key_block = (hunk, commit, date, path, lineno, [text[begin.start():]])
                rest = text[:begin.start()]
        for rule, value in find_in_line(rest):
            record(rule, value, commit, date, path, lineno)
    if key_block:
        close_block()

    result = []
    for entry in findings.values():
        value = entry.pop("_value")
        entry["in_head"] = any(in_head(repo, p, value) for p in entry["paths"])
        result.append(entry)
    return sorted(result, key=lambda e: (not e["in_head"], e["rule"], e["first_date"]))


def context(repo: Path, spec: str, radius: int) -> str:
    """Lines around <commit>:<path>:<line>, with every recognised secret masked."""
    try:
        commit, rest = spec.split(":", 1)
        path, line = rest.rsplit(":", 1)
        center = int(line)
    except ValueError as error:
        raise ScanError("--context needs <commit>:<path>:<line>") from error
    shown = git(repo, "show", f"{commit}:{path}")
    if shown.returncode != 0:
        raise ScanError(f"cannot read {path} at {commit}")
    out, in_key = [], False
    for number, text in enumerate(shown.stdout.splitlines(), start=1):
        is_key_line = in_key or bool(KEY_BEGIN.search(text))
        in_key = is_key_line and not KEY_END.search(text)
        if abs(number - center) > radius:
            continue
        shown_text = "[private key material]" if is_key_line else mask_line(text, number == center)
        out.append(f"{number:6} | {shown_text}")
    return "\n".join(out)


def mask_line(text: str, finding_line: bool = False) -> str:
    """Mask everything on a line that could be a secret, recognised or not."""
    for rule, value in find_in_line(text):
        text = text.replace(value, mask(rule, value))
    text = CONTEXT_ASSIGN.sub(lambda m: f"{m.group(1)}…({len(m.group(2))} chars)", text)
    text = URL_PASSWORD.sub(lambda m: f"{m.group(1)}…{m.group(3)}", text)
    # Quoted strings: all of them on the finding's own line, elsewhere any that hold a digit or symbol.
    text = QUOTED.sub(
        lambda m: m.group(0) if not finding_line and re.fullmatch(r"[\"'][a-z ]*[\"']", m.group(0))
        else f"…({len(m.group(0)) - 2} chars)",
        text,
    )
    return RANDOM_LOOKING.sub(
        lambda m: m.group(0) if entropy(m.group(0)) < 3.0 or m.group(0).isalpha() else f"…({len(m.group(0))} chars)",
        text,
    )


def load_key(path: Path) -> bytes:
    """The local HMAC key, created (owner-only) on first use."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(token_source.token_hex(32))
    return bytes.fromhex(path.read_text().strip())


def load_allow(path: str | None) -> frozenset:
    if not path:
        return frozenset()
    lines = Path(path).read_text().splitlines()
    return frozenset(l.split("#", 1)[0].strip() for l in lines if l.split("#", 1)[0].strip())


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo")
    parser.add_argument("--reflog", action="store_true", help="also scan commits only in the reflog")
    parser.add_argument("--allow", help="file of allowed fingerprints")
    parser.add_argument("--key-file", default=str(Path.home() / ".claude" / "secret-history-scan.key"),
                        help="HMAC key for fingerprints (created on first use)")
    parser.add_argument("--out", help="write findings as JSON to this file")
    parser.add_argument("--context", metavar="COMMIT:PATH:LINE", help="print masked lines around a finding")
    parser.add_argument("--radius", type=int, default=3, help="lines of context on each side")
    args = parser.parse_args(argv)
    repo = Path(args.repo)
    try:
        if git(repo, "rev-parse", "--git-dir").returncode != 0:
            print(f"not a git repository: {repo}", file=sys.stderr)
            return 2
        if args.context:
            print(context(repo, args.context, args.radius))
            return 0
        findings = scan(repo, load_key(Path(args.key_file)), args.reflog, load_allow(args.allow))
        text = json.dumps(findings, indent=2)
        if args.out:
            Path(args.out).write_text(text + "\n")
    except (ScanError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(text)
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover - exercised by test_cli_exit_codes_and_output
    sys.exit(main(sys.argv[1:]))
