#!/usr/bin/env python3
"""Check every skill in this repository the way claude.ai and the API check them on upload.

For each top-level directory that holds a SKILL.md:
  - the frontmatter (between the first two `---` lines) is valid YAML (strict: yaml.safe_load);
  - only the keys uploads to claude.ai and the API accept (name, description, license, allowed-tools,
    metadata, compatibility), so every skill here can also be uploaded there; Claude Code-only keys
    such as argument-hint are refused on purpose (add them to ALLOWED_KEYS if that changes);
  - `name` is lowercase letters, digits and hyphens, at most 64 characters, equals the directory, and
    doesn't contain the reserved words "anthropic" or "claude";
  - `description` is present, at most 1024 characters, and has no `<` or `>` (read as XML tags);
  - every relative Markdown link in the skill's .md files points at a file inside the repository.
And for the README: every skill has a row linking to its SKILL.md, and every skill link resolves.

Usage: python3 tools/validate_skills.py [REPO_ROOT]   (exit 1 and one line per problem if any fail)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

import yaml

NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
RESERVED = ("anthropic", "claude")
ALLOWED_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
# [text](target "title"), with the target optionally in <...>; titles in "", '' or ().
LINK = re.compile(r"\]\(\s*(<[^>]*>|[^\s()]*(?:\([^\s()]*\)[^\s()]*)*)(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)")
# Reference-style definitions: [label]: target
REFERENCE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)")
INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1")
EXTERNAL = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*:|//|#|~)")
# Fenced code blocks (``` or ~~~, three or more): links inside them are examples. A backtick fence's
# info string can't contain backticks, so ```code``` on one line is inline code, not a fence.
FENCE = re.compile(r"^ {0,3}(`{3,}(?!.*`)|~{3,})")


def frontmatter(text: str) -> str | None:
    """The YAML between a leading `---` line and the next `---` line, or None."""
    lines = text.lstrip("\ufeff").splitlines()          # a UTF-8 byte-order mark is not content
    if not lines or lines[0].rstrip() != "---":
        return None
    for i, line in enumerate(lines[1:], start=1):
        if line.rstrip() == "---":                       # an indented --- belongs to a block scalar
            return "\n".join(lines[1:i])
    return None


def check_skill(directory: Path) -> list[str]:
    """Problems with one skill directory's SKILL.md frontmatter."""
    where = f"{directory.name}/SKILL.md"
    raw = frontmatter((directory / "SKILL.md").read_text(encoding="utf-8"))
    if raw is None:
        return [f"{where}: no frontmatter (a `---` line, YAML, then a `---` line)"]
    try:
        meta = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        return [f"{where}: frontmatter is not valid YAML: {str(e).splitlines()[0]}"]
    if not isinstance(meta, dict):
        return [f"{where}: frontmatter is not a mapping"]

    problems = []
    unknown = sorted(set(map(str, meta)) - ALLOWED_KEYS)
    if unknown:
        problems.append(f"{where}: frontmatter keys {unknown} are not accepted on upload "
                        f"(allowed: {sorted(ALLOWED_KEYS)})")
    name = meta.get("name")
    if not isinstance(name, str) or not NAME.fullmatch(name) or len(name) > MAX_NAME:
        problems.append(f"{where}: name {name!r} must be lowercase letters, digits and single hyphens, "
                        f"at most {MAX_NAME} characters")
    elif any(word in name for word in RESERVED):
        problems.append(f"{where}: name {name!r} contains a reserved word ({', '.join(RESERVED)})")
    elif name != directory.name:
        problems.append(f"{where}: name {name!r} differs from its directory {directory.name!r}")

    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        problems.append(f"{where}: description is missing")
    else:
        if len(description) > MAX_DESCRIPTION:
            problems.append(f"{where}: description is {len(description)} characters (at most {MAX_DESCRIPTION})")
        if "<" in description or ">" in description:
            problems.append(f"{where}: description contains < or > (write placeholders as FILE, N, ...)")
    return problems


def links(text: str) -> list[str]:
    """Relative link targets in Markdown text, outside fenced code blocks."""
    targets, fence = [], None
    for line in text.splitlines():
        marker = FENCE.match(line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and line.strip() == token:
                fence = None
            continue
        if fence is not None:
            continue                                     # fenced code: examples
        # Indented lines are checked too: they are usually nested list items. Put code examples
        # with links in fences.
        line = INLINE_CODE.sub("", line)
        targets.extend(t.strip("<>") for t in LINK.findall(line))
        targets.extend(t.strip("<>") for t in REFERENCE.findall(line))
    # A target with a space can only come from <...>: a template placeholder such as <repo url>.
    return [t for t in targets if t and " " not in t and not EXTERNAL.match(t)]


def check_links(md: Path, root: Path) -> list[str]:
    """Relative links in one Markdown file that point at nothing."""
    problems = []
    for target in links(md.read_text(encoding="utf-8")):
        path = unquote(re.split(r"[#?]", target, maxsplit=1)[0])
        if not path:
            continue
        resolved = (md.parent / path).resolve()
        if not resolved.is_relative_to(root):
            problems.append(f"{md.relative_to(root)}: link to {target} leaves the repository")
        elif not resolved.exists():
            problems.append(f"{md.relative_to(root)}: link to {target} points at nothing")
    return problems


def check_readme(root: Path, skills: list[str]) -> list[str]:
    readme = root / "README.md"
    if not readme.exists():
        return ["README.md is missing"]
    text = readme.read_text(encoding="utf-8")
    return [f"README.md: no row for skill {name} (a link to {name}/SKILL.md)"
            for name in skills if f"({name}/SKILL.md)" not in text]


def skill_dirs(root: Path) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def validate(root: Path) -> list[str]:
    dirs = skill_dirs(root)
    problems = []
    for directory in dirs:
        problems += check_skill(directory)
        for md in sorted(directory.rglob("*.md")):
            problems += check_links(md, root)
    problems += check_readme(root, [d.name for d in dirs])
    problems += check_links(root / "README.md", root) if (root / "README.md").exists() else []
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    problems = validate(root)
    for problem in problems:
        print(problem)
    count = len(skill_dirs(root))
    print(f"{count} skills checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
