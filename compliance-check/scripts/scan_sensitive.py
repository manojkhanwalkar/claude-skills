#!/usr/bin/env python3
"""Scan source trees for regulated data that should not be there.

Finds leads for the compliance-check skill:
  pan       a 13-19 digit number that passes the Luhn check and has a card-brand
            prefix (possible primary account number, PCI DSS 3.x)
  test-pan  a well-known payment-network test number (fine in tests, never in prod config)
  ssn       a US Social Security number in NNN-NN-NNNN form with valid ranges
  example-ssn  a well-known placeholder SSN such as 123-45-6789
  sad       a field or key that looks like sensitive authentication data
            (CVV/CVC, track data, PIN block) - storing it after authorization is
            prohibited (PCI DSS 3.3.1)
  log-pii   a log/print call that mentions a sensitive field name

Hits in test paths are tagged [test] (JSON: "in_test": true). Synthetic data in
tests is usually fine; real-looking data in tests or fixtures that ship is not.

Every hit is a lead, not a finding: read the code before reporting it.
Matched values are never printed in full - only the last four characters.

Usage:
  scan_sensitive.py [PATH ...]           scan files or directories (default .)
  scan_sensitive.py --files-from -       read file paths from stdin (e.g. git diff --name-only)
  scan_sensitive.py --json ...           one JSON object per line instead of text

Standard library only. Reads files as data; never executes or imports them.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Iterator, NamedTuple

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_LINE_CHARS = 10_000
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "target", "build", "dist", "out",
    ".gradle", ".idea", ".venv", "venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".tox", "coverage", "htmlcov", ".next", "vendor",
}
SKIP_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".jar", ".class",
    ".gz", ".tar", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".so",
    ".dll", ".exe", ".bin", ".lock", ".min.js", ".map",
)

# Well-known test PANs published by card networks and processors.
TEST_PANS = {
    "4111111111111111", "4012888888881881", "4222222222222", "4242424242424242",
    "4000056655665556", "5555555555554444", "5105105105105100", "2223003122003222",
    "5200828282828210", "378282246310005", "371449635398431", "378734493671000",
    "6011111111111117", "6011000990139424", "3530111333300000", "3566002020360505",
    "30569309025904", "38520000023237", "6200000000000005", "4000000000000002",
    "4000000000009995", "4000002500003155",
}

# Placeholder SSNs that appear in documentation and samples (and the famous
# Woolworth wallet-card number). Never issued to a real person for that use.
EXAMPLE_SSNS = {"123-45-6789", "078-05-1120", "219-09-9999", "111-11-1111", "222-22-2222", "333-33-3333"}

PAN_CANDIDATE = re.compile(r"(?<![\d.])(?:\d[ -]?){12,18}\d(?![\d.])")
# Brand prefixes: Visa 4; Mastercard 51-55, 2221-2720; Amex 34/37; Discover 6011/64/65;
# Diners 36/38/300-305; JCB 3528-3589; UnionPay 62; Maestro 50/56-58/6.
BRAND_PREFIX = re.compile(
    r"^(4|5[1-5]|2(2[2-9][1-9]|2[3-9]\d|[3-6]\d\d|7[01]\d|720)|3[47]|6011|6[45]|"
    r"3(0[0-5]|[68])|35(2[89]|[3-8]\d)|62|5[06-8])"
)
SSN = re.compile(r"(?<![\d-])(?!000|666|9\d\d)(\d{3})-(?!00)(\d{2})-(?!0000)(\d{4})(?![\d-])")
# Matched against a normalised copy of the line (camelCase split with "_", lower
# case) so snake_case, camelCase and SCREAMING_CASE names all hit.
SAD_FIELD = re.compile(
    r"(?<![a-z0-9])(cvv2?|cvc2?|cav2|card_?verification(_?(code|value))?|security_?code|"
    r"track_?[12]|track_?data|mag_?stripe|pin_?block)(?![a-z0-9])"
)
CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def normalise(line: str) -> str:
    return CAMEL.sub("_", line).lower()


LOG_CALL = re.compile(
    r"\b(log(ger)?|LOG|LOGGER|console|logging|Log|slf4j|print(ln|f)?|System\.(out|err))"
    r"\s*(\.\s*\w+)?\s*\(",
)
SENSITIVE_NAME = re.compile(
    r"(ssn|social_?security|tax_?id|\btin\b|\bpan\b|card_?number|cc_?num|account_?number|"
    r"iban|routing_?number|cvv|cvc|dob\b|date_?of_?birth|passport|driver_?licen[cs]e|"
    r"password|passwd|secret|api_?key|access_?token|credit_?report|first_?name|"
    r"last_?name|full_?name|email|phone|address)",
    re.IGNORECASE,
)
DIGIT_ONLY = re.compile(r"\D")


TEST_PATH = re.compile(
    r"(^|[/\\])(tests?|__tests__|spec|fixtures?|testdata|src[/\\]test)([/\\]|$)|"
    r"(Test|Tests|IT|Spec)\.\w+$|(_test|\.test|\.spec|test_[^/\\]*)\.\w+$"
)


class Hit(NamedTuple):
    path: str
    line: int
    kind: str
    detail: str
    in_test: bool = False


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = ord(ch) - 48
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def mask(value: str) -> str:
    return "…" + value[-4:]


def scan_line(path: str, lineno: int, line: str) -> Iterator[Hit]:
    if len(line) > MAX_LINE_CHARS:
        line = line[:MAX_LINE_CHARS]
    for m in PAN_CANDIDATE.finditer(line):
        digits = DIGIT_ONLY.sub("", m.group(0))
        if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
            continue
        if digits in TEST_PANS:
            yield Hit(path, lineno, "test-pan", mask(digits))
        elif luhn_ok(digits) and BRAND_PREFIX.match(digits):
            yield Hit(path, lineno, "pan", f"{len(digits)} digits {mask(digits)}")
    for m in SSN.finditer(line):
        kind = "example-ssn" if m.group(0) in EXAMPLE_SSNS else "ssn"
        yield Hit(path, lineno, kind, mask(m.group(0)))
    sad = SAD_FIELD.search(normalise(line))
    if sad:
        yield Hit(path, lineno, "sad", sad.group(0))
    if LOG_CALL.search(line):
        name = SENSITIVE_NAME.search(line)
        if name:
            yield Hit(path, lineno, "log-pii", name.group(0))


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
    if path.lower().endswith(SKIP_SUFFIXES):
        return
    try:
        if os.path.islink(path) or os.path.getsize(path) > MAX_FILE_BYTES:
            return
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return
    if b"\0" in data[:8192]:
        return  # binary
    text = data.decode("utf-8", errors="replace")
    in_test = bool(TEST_PATH.search(path))
    for lineno, line in enumerate(text.splitlines(), start=1):
        for hit in scan_line(path, lineno, line):
            yield hit._replace(in_test=in_test)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="files or directories (default .)")
    ap.add_argument("--files-from", metavar="FILE", help="read paths, one per line ('-' for stdin)")
    ap.add_argument("--json", action="store_true", help="emit JSON lines")
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
            if args.json:
                print(json.dumps(hit._asdict()))
            else:
                tag = " [test]" if hit.in_test else ""
                print(f"{hit.path}:{hit.line}: {hit.kind}: {hit.detail}{tag}")
    print(f"# {count} lead(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
