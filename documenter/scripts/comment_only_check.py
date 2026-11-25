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

_STRINGS = (r'"""[\s\S]*?"""'              # Java/Kotlin/Swift text blocks, C# raw strings
            r'|"(?:\\.|[^"\\\n])*"'
            r'|`(?:\\.|[^`\\])*`')          # Go raw strings, JS template literals
_COMMENT = r"(?P<c>/\*[\s\S]*?\*/|//[^\n]*)"
_LEXER = {
    # Rust uses ' for lifetimes too, so only a short literal counts as a char there.
    ".rs": re.compile(_COMMENT + r'|(?P<s>b?r(?P<h>#*)"[\s\S]*?"(?P=h)|' + _STRINGS
                      + r"|'(?:\\.{1,10}|[^'\\\n])')"),
    ".cs": re.compile(_COMMENT + r'|(?P<s>@"(?:""|[^"])*"|' + _STRINGS + r"|'(?:\\.|[^'\\\n])*')"),
    ".swift": re.compile(_COMMENT + r'|(?P<s>(?P<h>#+)"[\s\S]*?"(?P=h)|' + _STRINGS + r")"),
    # JavaScript family: a regex literal candidate; split_c_like checks it isn't a division.
    "js": re.compile(_COMMENT + r"|(?P<s>" + _STRINGS + r"|'(?:\\.|[^'\\\n])*')"
                     r"|(?P<r>/(?![/*])(?:\\.|\[(?:\\.|[^\]\\\n])*\]|[^/\\\n\[])+/)"),
    "other": re.compile(_COMMENT + r"|(?P<s>" + _STRINGS + r"|'(?:\\.|[^'\\\n])*')"),
}
JS = {".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"}
_REGEX_BEFORE = re.compile(r"(?:^|[(,=:\[!&|?{};+\-*%<>~^]|\b(?:return|typeof|case|do|else|in|of|"
                           r"void|yield|await|delete|throw|new))\s*$")
DIRECTIVE = re.compile(
    r"^(?:#!|//go:|//line |//export |//extern |//\s*\+[\w./-]+|///\s*<(?:reference|amd)"
    r"|//\s*#(?:region|endregion)|(?:/\*|//)\s*(?:eslint|global|jshint)\b)"
    r"|@ts-(?:ignore|expect-error|nocheck|check)|eslint-(?:disable|enable|env)|prettier-ignore"
    r"|webpack[A-Z]\w*\s*:|[@#]__PURE__|istanbul ignore|c8 ignore|NOSONAR|NOPMD|noinspection"
    r"|ReSharper|CHECKSTYLE|@formatter:|nolint|noqa|type:\s*ignore|pragma:|fmt:\s*(?:off|on|skip)"
    r"|pylint:|mypy:|pyright:|isort:|biome-ignore|tslint:|deno-lint-ignore|-\*-\s*coding"
    r"|swiftlint:|@jsx|@flow\b|NON-NLS|@vite-ignore"
    r"|@(?:Router|Param|Success|Failure|Summary|Description|Tags|Accept|Produce|Security|ID)\b")


def git(repo, *args):
    """Run git in repo and return its stdout; raise CalledProcessError on failure."""
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def changed_files(repo, start):
    """Return (changes as (status, path, old_path), untracked files that aren't source).

    Untracked source and package doc files count as added ('A'); other untracked files (local
    settings, build output not ignored) are returned apart, since the clean-tree rule allows them.
    """
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
    others = []
    for path in filter(None, git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0")):
        if kind(path) or os.path.basename(path) in PACKAGE_DOC:
            changes.append(("A", path, None))
        else:
            others.append(path)
    return changes, others


def kind(path):
    """Return 'c', 'python' or None for the file's language family."""
    ext = os.path.splitext(path)[1].lower()
    return "c" if ext in C_LIKE else "python" if ext in PYTHON else None


def _lexer(path):
    ext = os.path.splitext(path)[1].lower()
    return _LEXER.get(ext) or _LEXER["js" if ext in JS else "other"]


def split_c_like(text, path):
    """Return (code lines as (line number, normalised text), directive comments) of a C-like file.

    String literals are kept verbatim (their whitespace protected from normalisation); comments
    are dropped but keep their line breaks, so line numbers still match the file.
    """
    lexer, jsx = _lexer(path), path.lower().endswith((".jsx", ".tsx"))
    directives, pieces, pos, scan = [], [], 0, 0
    while (m := lexer.search(text, scan)):
        before = text[pos:m.start()]
        comment = m.group("c")
        if m.lastgroup == "r" and not _REGEX_BEFORE.search("".join(pieces[-1:]) + before):
            scan = m.start() + 1                 # a division, not a regex literal
            continue
        if comment and jsx and comment.startswith("//") \
                and text[text.rfind("\n", 0, m.start()) + 1:m.start()].strip() \
                and not text[m.start() - 1].isspace():
            scan = m.end()                       # JSX text such as https://...: the line is code
            continue
        pieces.append(before)
        if comment:
            if DIRECTIVE.search(comment):
                directives.append(" ".join(comment.split()))
            pieces.append("\n" * comment.count("\n"))
        else:                                    # a string or regex literal: protect its spaces
            pieces.append(m.group().replace(" ", "\x01").replace("\t", "\x02"))
        pos = scan = m.end()
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


def _shown(line):
    return line.replace("\x01", " ").replace("\x02", "\t")[:80]


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
            problems.append(f"line {n}: code changed: {_shown(line)}")
            break
    else:
        if len(old_lines) > len(new_code):
            problems.append(f"code removed: {_shown(old_lines[len(new_code)])}")
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
    """Return (number of files checked, list of 'path: problem' strings, untracked non-source)."""
    failures, (changes, others) = [], changed_files(repo, start)
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
    return len(changes), failures, others


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
    count, failures, others = check(repo, args.start)
    for path in others:
        print(f"NOTE {path}: untracked and not source, so not checked; leave it out of the commit")
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        print(f"COMMENT-ONLY CHECK: FAIL ({len(failures)} problems in {count} files)")
        return 1
    print(f"COMMENT-ONLY CHECK: PASS ({count} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
