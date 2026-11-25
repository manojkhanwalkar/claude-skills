#!/usr/bin/env python3
"""Prove that the changes since a commit touch comments only.

Usage: comment_only_check.py START [--repo DIR]

Compares every file changed since START (committed, staged, unstaged, and untracked source files)
with its START version:
  * Java, Kotlin, TypeScript, JavaScript, Go, Rust, C# and Swift: the code left after removing
    comments must be the same line for line (indentation and blank lines aside).
  * Python: the syntax trees must match once module, class and function docstrings are removed.
  * Every language: tool directives written as comments (//go:build, @ts-ignore, eslint-disable,
    # noqa, # type: ignore, /// <reference>, ...) must not change, since they are code to a tool.
  * A new file passes only as a package doc file (package-info.java, doc.go) holding comments
    and its package clause. A renamed, deleted or unsupported file fails.
Prints one FAIL line per problem, then a summary line. Exit 0 on PASS, 1 on FAIL, 2 on bad usage.
Stdlib only.
"""
import argparse
import ast
import io
import os
import re
import subprocess
import sys
import tokenize

C_LIKE = {".java", ".kt", ".kts", ".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs",
          ".go", ".rs", ".cs", ".swift"}
PYTHON = {".py", ".pyi"}
PACKAGE_DOC = {"package-info.java": re.compile(r"package\s+[\w.]+\s*;"),
               "doc.go": re.compile(r"package\s+\w+")}

_STRINGS = (r'"""[\s\S]*?"""'              # Java/Kotlin/Swift text blocks
            r'|"(?:\\.|[^"\\\n])*"'
            r'|`(?:\\.|[^`\\])*`')          # Go raw strings, JS template literals
_LEXER = {
    # Rust uses ' for lifetimes too, so only a one-character literal counts as a string there.
    "rust": re.compile(r"(/\*[\s\S]*?\*/|//[^\n]*)|(" + _STRINGS + r"|'(?:\\.{1,10}|[^'\\\n])')"),
    "other": re.compile(r"(/\*[\s\S]*?\*/|//[^\n]*)|(" + _STRINGS + r"|'(?:\\.|[^'\\\n])*')"),
}
DIRECTIVE = re.compile(
    r"^(?:#!|//go:|//line |//export |//extern |//\s*\+build|///\s*<(?:reference|amd)"
    r"|//\s*#(?:region|endregion))"
    r"|@ts-(?:ignore|expect-error|nocheck|check)|eslint-(?:disable|enable)|prettier-ignore"
    r"|webpack[A-Z]\w*\s*:|[@#]__PURE__|istanbul ignore|c8 ignore|NOSONAR|noinspection"
    r"|CHECKSTYLE|@formatter:|nolint|noqa|type:\s*ignore|pragma:|fmt:\s*(?:off|on|skip)"
    r"|-\*-\s*coding|swiftlint:|@jsx|@flow\b|NON-NLS|@vite-ignore")


def git(repo, *args):
    """Run git in repo and return its stdout; raise CalledProcessError on failure."""
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def changed_files(repo, start):
    """Return (status, path, old_path) for every change since start, untracked files as 'A'."""
    out = git(repo, "diff", "--name-status", "-z", "-M", start).split("\0")
    changes, i = [], 0
    while i < len(out) - 1:
        status = out[i]
        if status[0] in "RC":
            changes.append((status[0], out[i + 2], out[i + 1]))
            i += 3
        else:
            changes.append((status[0], out[i + 1], None))
            i += 2
    for path in git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0"):
        if path and (kind(path) or os.path.basename(path) in PACKAGE_DOC):
            changes.append(("A", path, None))
    return changes


def kind(path):
    """Return 'c', 'python' or None for the file's language family."""
    ext = os.path.splitext(path)[1].lower()
    return "c" if ext in C_LIKE else "python" if ext in PYTHON else None


def split_c_like(text, path):
    """Return (code lines as (line number, normalised text), directive comments) of a C-like file."""
    lexer = _LEXER["rust" if path.endswith(".rs") else "other"]
    directives, pieces, pos = [], [], 0
    for m in lexer.finditer(text):
        pieces.append(text[pos:m.start()])
        if m.group(1):                       # a comment: keep its line breaks, drop its text
            comment = m.group(1)
            if DIRECTIVE.search(comment):
                directives.append(" ".join(comment.split()))
            pieces.append("\n" * comment.count("\n"))
        else:
            pieces.append(m.group(2))
        pos = m.end()
    pieces.append(text[pos:])
    code = "".join(pieces).split("\n")
    return [(n, " ".join(line.split())) for n, line in enumerate(code, 1) if line.strip()], directives


def _strip_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:]
    return ast.dump(tree)


def python_shape(text):
    """Return (syntax tree without docstrings, directive comments) of Python source."""
    tree = ast.parse(text)
    directives = [tok.string for tok in tokenize.generate_tokens(io.StringIO(text).readline)
                  if tok.type == tokenize.COMMENT and DIRECTIVE.search(tok.string)]
    return _strip_docstrings(tree), directives


def compare(path, old, new):
    """Return a list of problems where new differs from old outside comments."""
    if kind(path) == "python":
        try:
            old_shape, new_shape = python_shape(old), python_shape(new)
        except (SyntaxError, ValueError, tokenize.TokenError) as e:
            return [f"does not parse ({e.__class__.__name__}); check it by eye"]
        problems = [] if old_shape[0] == new_shape[0] else ["code changed (syntax tree differs)"]
        if old_shape[1] != new_shape[1]:
            problems.append("a tool directive comment changed")
        return problems
    if path.endswith(".go") and re.search(r'^import\s+"C"', old, re.M) and old != new:
        return ['cgo file: the comment above import "C" is C code; check it by eye']
    (old_code, old_dir), (new_code, new_dir) = split_c_like(old, path), split_c_like(new, path)
    problems = []
    old_lines = [t for _, t in old_code]
    for i, (n, line) in enumerate(new_code):
        if i >= len(old_lines) or old_lines[i] != line:
            problems.append(f"line {n}: code changed: {line[:80]}")
            break
    else:
        if len(old_lines) > len(new_code):
            problems.append(f"code removed: {old_lines[len(new_code)][:80]}")
    if old_dir != new_dir:
        problems.append("a tool directive comment changed")
    return problems


def check_new(path, text):
    """Return problems with a file created since START (only package doc files may be new)."""
    rule = PACKAGE_DOC.get(os.path.basename(path))
    if not rule:
        return ["new file; this skill only edits comments in existing files"]
    code, directives = split_c_like(text, path)
    if len(code) != 1 or not rule.fullmatch(code[0][1]) or directives:
        return ["new package doc file holds more than comments and its package clause"]
    return []


def check(repo, start):
    """Return (number of files checked, list of 'path: problem' strings)."""
    failures, changes = [], changed_files(repo, start)
    for status, path, old_path in changes:
        if status == "R":
            failures.append(f"{path}: renamed from {old_path}; this skill never moves files")
        elif status == "D":
            failures.append(f"{path}: deleted")
        elif status not in "AM":
            failures.append(f"{path}: changed in an unexpected way (git status {status})")
        elif not kind(path) and os.path.basename(path) not in PACKAGE_DOC:
            failures.append(f"{path}: not a supported source file")
        else:
            with open(os.path.join(repo, path), encoding="utf-8", errors="replace") as f:
                new = f.read().replace("\r\n", "\n")
            if status == "A":
                problems = check_new(path, new)
            else:
                old = git(repo, "show", f"{start}:{path}").replace("\r\n", "\n")
                problems = compare(path, old, new)
            failures.extend(f"{path}: {p}" for p in problems)
    return len(changes), failures


def main(argv):
    parser = argparse.ArgumentParser(description="Prove the changes since START touch comments only.")
    parser.add_argument("start", help="the commit the edits began from")
    parser.add_argument("--repo", default=".", help="the repository (default: current directory)")
    args = parser.parse_args(argv)
    try:
        repo = git(args.repo, "rev-parse", "--show-toplevel").strip()
        git(repo, "rev-parse", "--verify", "--quiet", f"{args.start}^{{commit}}")
    except subprocess.CalledProcessError as e:
        print(f"error: {e.stderr.strip() or 'not a commit: ' + args.start}", file=sys.stderr)
        return 2
    count, failures = check(repo, args.start)
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        print(f"COMMENT-ONLY CHECK: FAIL ({len(failures)} problems in {count} files)")
        return 1
    print(f"COMMENT-ONLY CHECK: PASS ({count} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
