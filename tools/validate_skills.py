#!/usr/bin/env python3
"""Check every skill in this repository the way claude.ai and the API check them on upload.

For each top-level directory that holds a SKILL.md:
  - the frontmatter (between the first two `---` lines) is valid YAML (strict: yaml.safe_load);
  - only the keys uploads to claude.ai and the API accept (name, description, license, allowed-tools,
    metadata, compatibility), so every skill here can also be uploaded there; Claude Code-only keys
    such as argument-hint are refused on purpose (add them to ALLOWED_KEYS if that changes);
  - `name` is lowercase letters, digits and hyphens, at most 64 characters, equals the directory, and
    doesn't contain the reserved words "anthropic" or "claude";
  - `description` is present, at most 1024 characters, has no `<` or `>` (read as XML tags) and has an
    `Args` part listing the arguments;
  - every relative Markdown link in the skill's .md files points at a file inside the repository, and
    every `references/...` or `scripts/...` path quoted in SKILL.md (and every ${CLAUDE_SKILL_DIR}/... path)
    exists (and, `..` resolved, stays there), in the skill itself or, for a pointer to a sibling's file,
    in another skill; a SKILL.md never names ~/.claude/skills/... (that is only where a clone lives: a
    plugin install puts the skills elsewhere, so commands use ${CLAUDE_SKILL_DIR});
  - no private project name (PRIVATE_NAMES) appears in a tracked text file (git ls-files; outside git,
    every file but hidden folders and __pycache__); the repository is public.
And for the README: every skill has a row linking to its SKILL.md and a change-log row naming it, and
every skill link resolves. And for the plugin: when .claude-plugin/plugin.json exists, it is valid JSON
with a MAJOR.MINOR.PATCH `version`, and its `skills` list names every skill directory exactly once, as
./<dir>, and nothing else, so a new skill can't ship without being installable; the marketplace's root
entries ("source": "./") then include one with its `name`, all carry that `name`, and no `skills` or `strict: false` (with a plugin.json,
an entry's skills are appended to the manifest's, and `strict: false` beside them is a load conflict).
Without a plugin.json, the `skills` lists of the marketplace's root entries are checked the same way.

Warnings (printed, never failing): a description over LISTING_BUDGET characters, the per-skill share
that keeps the whole skill listing within Claude Code's budget.

Usage: python3 tools/validate_skills.py [REPO_ROOT]   (exit 1 and one line per problem if any fail)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import yaml

NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
LISTING_BUDGET = 300
ARGS = re.compile(r"\bArgs\b")
# Private project names, as SHA-256 of the lowercase name, so they aren't spelled out or greppable here
# (a short name's hash can still be guessed: this keeps names out of the text, it doesn't hide them).
# Add one: python3 -c "import hashlib; print(hashlib.sha256(b'myproject').hexdigest(), len('myproject'))"
PRIVATE_NAMES = {
    ("eebaee4e5d0467b5d9be37101f0523818a0b93a9aacb7b59deb7161fb3a02fc4", 11),
    ("ef4afaf1de7a3bf1992c3f7ca255e648105e840bec76673be0aad86d730ca012", 19),
}
# A word, with -, _ and . joining its parts: "my-project" is matched as "myproject".
WORD = re.compile(r"[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*")
SEPARATORS = re.compile(r"[-_.]")
TEXT_SUFFIXES = {".md", ".py", ".sh", ".yml", ".yaml", ".json", ".toml", ".txt"}
# `references/x.md` or `scripts/x.py` quoted in a SKILL.md; ~/.claude/skills/<path> and
# ${CLAUDE_SKILL_DIR}/<path> anywhere in it.
QUOTED_PATH = re.compile(r"`((?:references|scripts)/[A-Za-z0-9_./-]+)`")
SKILLS_PATH = re.compile(r"~/\.claude/skills/([A-Za-z0-9_./-]*[A-Za-z0-9_-])")
SKILL_DIR_PATH = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/([A-Za-z0-9_./-]*[A-Za-z0-9_-])")
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
        if not ARGS.search(description):
            problems.append(f"{where}: description has no Args part (end it with \"Args - [PR] [--flag]\" or \"Args - none\")")
    return problems


def description_length(directory: Path) -> int:
    """Characters in a skill's description, or 0 when check_skill already reports it unreadable."""
    raw = frontmatter((directory / "SKILL.md").read_text(encoding="utf-8"))
    try:
        meta = yaml.safe_load(raw) if raw is not None else None
    except yaml.YAMLError:
        return 0
    description = meta.get("description") if isinstance(meta, dict) else None
    return len(description) if isinstance(description, str) else 0


def inside(path: Path, base: Path) -> bool:
    """True when path exists and, with `..` and symlinks resolved, stays inside base."""
    return path.exists() and path.resolve().is_relative_to(base.resolve())


def check_paths(directory: Path, root: Path, skills: list[Path]) -> list[str]:
    """Quoted references/ and scripts/ paths and ${CLAUDE_SKILL_DIR}/ paths in SKILL.md that point at nothing
    (or leave the repository), and any ~/.claude/skills/ path, which breaks a plugin install."""
    text = (directory / "SKILL.md").read_text(encoding="utf-8")
    where = f"{directory.name}/SKILL.md"
    problems = []
    for path in sorted(set(QUOTED_PATH.findall(text))):
        # Its own file, or a pointer to a sibling's ("perf-review's `references/data-access.md`").
        if not any(inside(d / path, d) for d in [directory, *skills]):
            problems.append(f"{where}: {path} exists in no skill")
    for path in sorted(set(SKILLS_PATH.findall(text))):
        problems.append(f"{where}: ~/.claude/skills/{path} only exists in a clone; a plugin install puts "
                        "the skills elsewhere (write ${CLAUDE_SKILL_DIR}/...)")
    for path in sorted(set(SKILL_DIR_PATH.findall(text))):
        if not inside(directory / path, root):
            problems.append(f"{where}: ${{CLAUDE_SKILL_DIR}}/{path} points at nothing in this repository")
    return problems


def private_names(text: str) -> list[str]:
    """Words in text that contain a private project name (case-insensitive)."""
    found = []
    for word in set(WORD.findall(text)):
        lower = SEPARATORS.sub("", word.lower())
        if any(hashlib.sha256(lower[i:i + n].encode()).hexdigest() == digest
               for digest, n in PRIVATE_NAMES for i in range(len(lower) - n + 1)):
            found.append(word)
    return sorted(found)


def scanned_files(root: Path) -> list[Path]:
    """The repository's own text files: tracked ones (so a local venv or synced/ folder is skipped);
    outside a git checkout, every file except hidden folders (.github kept) and __pycache__."""
    try:
        listed = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True,
                                check=True, timeout=60).stdout.decode("utf-8").split("\0")
        files = [root / name for name in listed if name]
    except (OSError, subprocess.SubprocessError):
        files = [p for p in root.rglob("*")
                 if not any(part.startswith(".") and part != ".github" or part == "__pycache__"
                            for part in p.relative_to(root).parts[:-1])]
    return sorted(p for p in files if p.suffix in TEXT_SUFFIXES and p.is_file())


def check_private(root: Path) -> list[str]:
    """Files that name a private project, one problem per file with the words found."""
    problems = []
    for path in scanned_files(root):
        words = private_names(path.read_text(encoding="utf-8", errors="replace"))
        if words:
            problems.append(f"{path.relative_to(root)}: private project name in {', '.join(words)} "
                            "(this repo is public: use a generic example)")
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
    """README problems: a missing file, skill-table row, change-log section or change-log row naming a skill."""
    readme = root / "README.md"
    if not readme.exists():
        return ["README.md is missing"]
    text = readme.read_text(encoding="utf-8")
    problems = [f"README.md: no row for skill {name} (a link to {name}/SKILL.md)"
                for name in skills if f"({name}/SKILL.md)" not in text]
    log = re.split(r"^## Change log\s*$", text, maxsplit=1, flags=re.MULTILINE)
    if len(log) < 2:
        return problems + ["README.md: no \"## Change log\" section"]
    log = re.split(r"^#{1,2} ", log[1], maxsplit=1, flags=re.MULTILINE)[0]
    rows = [line for line in log.splitlines() if line.startswith("|")]
    for name in skills:
        word = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")
        if not any(word.search(row) for row in rows):
            problems.append(f"README.md: no change-log row names skill {name}")
    return problems


MARKETPLACE = Path(".claude-plugin/marketplace.json")
PLUGIN = Path(".claude-plugin/plugin.json")
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


def load_json(root: Path, rel: Path) -> tuple[object, list[str]]:
    """The parsed file and no problems, or None and the one problem that stops the check."""
    try:
        return json.loads((root / rel).read_text(encoding="utf-8")), []
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, [f"{rel}: not valid JSON: {e}"]


def root_entries(data: object) -> list[dict]:
    """The marketplace's plugin entries whose source is the repository root."""
    plugins = data.get("plugins") if isinstance(data, dict) else None
    return [p for p in (plugins if isinstance(plugins, list) else [])
            if isinstance(p, dict) and p.get("source") in ("./", ".")]


def check_skill_list(where: str, listed: list, skills: list[str]) -> list[str]:
    """Problems with a skills list: each skill directory exactly once as ./<dir>, and nothing else."""
    problems = [f"{where}: {entry!r} is listed more than once"
                for entry in sorted({e for e in listed if isinstance(e, str) and listed.count(e) > 1})]
    wanted = {f"./{name}" for name in skills}
    problems += [f"{where}: skill {name} is not in a plugin's skills list (add \"./{name}\")"
                 for name in skills if f"./{name}" not in listed]
    unknown = []
    for entry in listed:
        if (not isinstance(entry, str) or entry not in wanted) and entry not in unknown:
            unknown.append(entry)
    problems += [f"{where}: {entry!r} in a skills list is not a skill directory (write ./<dir>)"
                 for entry in unknown]
    return problems


def check_manifest(root: Path, skills: list[str]) -> list[str]:
    """Problems with plugin.json, and with marketplace root entries that would clash with it."""
    where = str(PLUGIN)
    data, problems = load_json(root, PLUGIN)
    if problems:
        return problems
    if not isinstance(data, dict):
        return [f"{where}: not a JSON object"]
    version = data.get("version")
    if not (isinstance(version, str) and SEMVER.fullmatch(version)):
        problems.append(f"{where}: version {version!r} is not MAJOR.MINOR.PATCH")
    listed = data.get("skills")
    if isinstance(listed, list):
        problems += check_skill_list(where, listed, skills)
    else:
        problems.append(f"{where}: no skills list")
    if not (root / MARKETPLACE).is_file():
        return problems
    market, bad = load_json(root, MARKETPLACE)
    if bad:
        return problems + bad
    entries = root_entries(market)
    if not any(entry.get("name") == data.get("name") for entry in entries):
        problems.append(f"{MARKETPLACE}: no entry with \"source\": \"./\" is named {data.get('name')!r}, "
                        "so the plugin can't be installed from the marketplace")
    for entry in entries:
        label = f"{MARKETPLACE}: entry {entry.get('name')!r}"
        if entry.get("name") != data.get("name"):
            problems.append(f"{label} is not named like plugin.json ({data.get('name')!r})")
        if "skills" in entry:
            problems.append(f"{label} lists skills; with a plugin.json, list them there only")
        if entry.get("strict") is False:
            problems.append(f"{label} sets strict: false; with a plugin.json, leave strict at its default")
    return problems


def check_marketplace(root: Path, skills: list[str]) -> list[str]:
    """Problems with the plugin's skill list: plugin.json's when it exists, else the marketplace's;
    none when the repository has neither."""
    if (root / PLUGIN).is_file():
        return check_manifest(root, skills)
    if not (root / MARKETPLACE).is_file():
        return []
    where = str(MARKETPLACE)
    data, problems = load_json(root, MARKETPLACE)
    if problems:
        return problems
    lists = [p["skills"] for p in root_entries(data) if isinstance(p.get("skills"), list)]
    if not lists:
        return [f"{where}: no plugin with \"source\": \"./\" has a skills list"]
    return check_skill_list(where, [entry for entries in lists for entry in entries], skills)


def skill_dirs(root: Path) -> list[Path]:
    """Top-level directories that hold a SKILL.md, sorted."""
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def validate(root: Path) -> list[str]:
    """Every hard problem in the repository; an empty list means the CI gate passes."""
    dirs = skill_dirs(root)
    problems = []
    for directory in dirs:
        problems += check_skill(directory)
        problems += check_paths(directory, root, dirs)
        for md in sorted(directory.rglob("*.md")):
            problems += check_links(md, root)
    problems += check_readme(root, [d.name for d in dirs])
    problems += check_marketplace(root, [d.name for d in dirs])
    problems += check_links(root / "README.md", root) if (root / "README.md").exists() else []
    problems += check_private(root)
    return problems


def warnings(root: Path) -> list[str]:
    """Soft limits: reported, never failing the run."""
    return [f"{d.name}/SKILL.md: description is {n} characters, over the {LISTING_BUDGET}-character "
            "listing budget (keep the whole skill listing small)"
            for d in skill_dirs(root) if (n := description_length(d)) > LISTING_BUDGET]


def main(argv: list[str]) -> int:
    """Print problems and warnings for REPO_ROOT (argv[1], default .); exit 1 on any problem."""
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    problems = validate(root)
    for problem in problems:
        print(problem)
    soft = warnings(root)
    prefix = "::warning::" if os.environ.get("GITHUB_ACTIONS") == "true" else "warning: "
    for warning in soft:
        print(prefix + warning)
    count = len(skill_dirs(root))
    print(f"{count} skills checked, {len(problems)} problem(s), {len(soft)} warning(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
