"""Scan a git repository's whole history for committed secrets (stdlib only).

Usage:
    python3 -I scan_history.py <repo> [--reflog] [--allow <file>] [--out <file.json>]

Reads every commit reachable from any ref (and the reflog with --reflog), looks at lines
each commit added, and reports secrets it recognises. A secret's value is never printed or
written: findings carry a masked form (first 4 characters and the length) and a SHA-256
fingerprint, which is what an allow-list file lists (one fingerprint per line, '#' comments).

Exit status: 0 no findings, 1 findings, 2 usage or git error.
"""

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

# Well-known token formats: (rule id, pattern, group holding the secret).
RULES = [
    ("aws-access-key-id", re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b"), 1),
    ("github-token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{36,})\b"), 1),
    ("github-fine-grained-pat", re.compile(r"\b(github_pat_[A-Za-z0-9_]{50,})\b"), 1),
    ("anthropic-api-key", re.compile(r"\b(sk-ant-[A-Za-z0-9_\-]{20,})"), 1),
    ("openai-api-key", re.compile(r"\b(sk-(?:proj-)?[A-Za-z0-9_\-]{32,})"), 1),
    ("slack-token", re.compile(r"\b(xox[abposr]-[A-Za-z0-9-]{10,})\b"), 1),
    ("google-api-key", re.compile(r"\b(AIza[0-9A-Za-z_\-]{35})\b"), 1),
    ("stripe-live-key", re.compile(r"\b((?:sk|rk)_live_[0-9A-Za-z]{24,})\b"), 1),
    ("private-key", re.compile(r"(-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----)"), 1),
    (
        "jwt",
        re.compile(r"\b(eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b"),
        1,
    ),
]

# A generic "name = 'value'" assignment counts only when the value looks random.
GENERIC = re.compile(
    r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?key|auth[_-]?token|token)\b"
    r"\s*[:=]\s*['\"]([^'\"\s]{12,})['\"]"
)
GENERIC_MIN_ENTROPY = 3.5
PLACEHOLDER = re.compile(r"(?i)(example|placeholder|changeme|dummy|xxxx|your[_-]|<|\$\{|\{\{)")


def entropy(value: str) -> float:
    """Shannon entropy in bits per character."""
    counts = Counter(value)
    return -sum(n / len(value) * math.log2(n / len(value)) for n in counts.values())


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def mask(value: str) -> str:
    return f"{value[:4]}…({len(value)} chars)"


def find_in_line(line: str):
    """Yield (rule, value) for each secret on one added line."""
    for rule, pattern, group in RULES:
        for match in pattern.finditer(line):
            yield rule, match.group(group)
    for match in GENERIC.finditer(line):
        value = match.group(1)
        if not PLACEHOLDER.search(value) and entropy(value) >= GENERIC_MIN_ENTROPY:
            yield "generic-secret-assignment", value


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, errors="replace", check=False
    )


def history(repo: Path, reflog: bool):
    """Yield (commit, date, path, line) for every line added anywhere in history."""
    args = ["log", "--all", "-p", "--no-color", "--no-ext-diff", "--no-renames", "--unified=0",
            "--format=COMMIT %H %cI"]
    if reflog:
        args.insert(2, "--reflog")
    with subprocess.Popen(
        ["git", "-C", str(repo), *args], stdout=subprocess.PIPE, text=True, errors="replace"
    ) as proc:
        commit = date = path = None
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            if line.startswith("COMMIT "):
                _, commit, date = line.split(" ", 2)
                path = None
            elif line.startswith("+++ "):
                path = line[6:] if line.startswith("+++ b/") else None
            elif line.startswith("+") and path is not None:
                yield commit, date, path, line[1:]
    if proc.returncode != 0:
        raise RuntimeError("git log failed")


def in_head(repo: Path, path: str, value: str) -> bool:
    shown = git(repo, "show", f"HEAD:{path}")
    return shown.returncode == 0 and value in shown.stdout


def scan(repo: Path, reflog: bool = False, allowed: frozenset = frozenset()) -> list:
    findings: dict = {}
    for commit, date, path, line in history(repo, reflog):
        for rule, value in find_in_line(line):
            fp = fingerprint(value)
            if fp in allowed:
                continue
            entry = findings.setdefault(fp, {
                "rule": rule, "masked": mask(value), "fingerprint": fp,
                "first_commit": commit, "first_date": date, "paths": [], "_value": value,
            })
            # git log runs newest first, so the last commit seen is the one that introduced it.
            entry["first_commit"], entry["first_date"] = commit, date
            if path not in entry["paths"]:
                entry["paths"].append(path)
    result = []
    for entry in findings.values():
        value = entry.pop("_value")
        entry["in_head"] = any(in_head(repo, p, value) for p in entry["paths"])
        result.append(entry)
    return sorted(result, key=lambda e: (not e["in_head"], e["rule"], e["first_date"]))


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
    parser.add_argument("--out", help="write findings as JSON to this file")
    args = parser.parse_args(argv)
    repo = Path(args.repo)
    if git(repo, "rev-parse", "--git-dir").returncode != 0:
        print(f"not a git repository: {repo}", file=sys.stderr)
        return 2
    try:
        findings = scan(repo, args.reflog, load_allow(args.allow))
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 2
    text = json.dumps(findings, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text)
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover - exercised by test_cli_exit_codes_and_output
    sys.exit(main(sys.argv[1:]))
