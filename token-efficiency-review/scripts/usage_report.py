#!/usr/bin/env python3
"""Summarise where Claude Code spent tokens, from the local session transcripts.

Reads ~/.claude/projects/<project>/<session>.jsonl (the main conversation) and
<session>/subagents/agent-<id>.jsonl (background agents), keeps the messages since a time, and
prints a Markdown report (or JSON with --json): token totals, the agents that used the most, the
tools whose results took the most context, the largest single results, CI polling, context
compactions, API errors (rate limits), the skills and slash commands used, and how much of Claude
Code's skill-listing budget the installed skills' descriptions take.

Privacy: it prints numbers, tool, skill and model names, a command's program name (plus a short
lowercase subcommand for a few known programs), and each agent's description, which the parent
model wrote when it started the agent (local-only text, never published). It never prints prompts,
file contents, command arguments or output, or any other transcript text, including in errors.

Usage: usage_report.py [--projects DIR] [--since TIME] [--days N] [--top N] [--json]
                       [--skills DIR] [--context TOKENS] [--desc-target N]
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Polling the anti-pattern way: a sleep, or a checks call that doesn't wait by itself. A single
# `gh pr checks --watch` in the background is the recommended pattern and is not counted.
SLEEP = re.compile(r"(^|[;&|]\s*)sleep\b")          # sleep as a command, not `grep sleep`
CHECKS = re.compile(r"\bgh (pr|run) checks\b")        # `gh run watch` waits by itself
PROGRAM = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,19}$")
SLASH = re.compile(r"<command-name>/?([A-Za-z0-9:_-]{1,64})</command-name>")   # a typed /command
ERROR_KIND = re.compile(r"^[a-z_]{1,30}$")
# Claude Code lists every skill as "- name: description" in a budget of 1% of the context window at
# about 4 characters per token, each description cut at 1,536 characters. Over budget, it drops the
# descriptions of some skills, which then trigger worse. SLASH_COMMAND_TOOL_CHAR_BUDGET overrides it.
LISTING_SHARE, CHARS_PER_TOKEN, MAX_DESC = 0.01, 4, 1536
# The second word is printed only when it is one of these well-known subcommands.
KNOWN = {
    "gh": {"pr", "run", "issue", "api", "repo", "release", "workflow", "search", "auth"},
    "git": {"status", "log", "diff", "show", "commit", "push", "pull", "fetch", "merge", "checkout",
            "switch", "branch", "worktree", "add", "rebase", "stash", "grep", "ls-files", "rev-parse"},
    "mvn": {"verify", "test", "install", "compile", "package", "clean"},
    "npm": {"test", "ci", "install", "run"},
    "docker": {"build", "run", "ps", "images", "compose", "logs"},
    "podman": {"build", "run", "ps", "images", "logs"},
    "systemctl": {"status", "start", "stop", "restart", "enable", "disable"},
}


def number(value) -> int:
    """A token count, or 0 for anything that isn't a plain number (never echoes the value)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def tokens_in(usage: dict) -> int:
    """Input tokens of one API call, cached or not."""
    return sum(number(usage.get(k)) for k in
               ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))


def command_head(command: str) -> str:
    """A command's program name, plus a short lowercase subcommand for a few known programs."""
    words = command.split()
    if not words:
        return "(command)"
    program = words[0].rsplit("/", 1)[-1]
    if not PROGRAM.match(program):
        return "(command)"
    if len(words) > 1 and words[1] in KNOWN.get(program, ()):
        return f"{program} {words[1]}"
    return program


def is_poll(command: str) -> bool:
    return bool(SLEEP.search(command)) or (bool(CHECKS.search(command)) and "--watch" not in command)


def clean(text: str) -> str:
    """Agent descriptions go into a table: one line, no pipes, at most 60 characters."""
    return re.sub(r"\s+", " ", re.sub(r"[|\r\n\t]", " ", text)).strip()[:60]


def result_chars(content) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(c.get("text", "")) for c in content
                   if isinstance(c, dict) and isinstance(c.get("text", ""), str))
    return 0


def parse_time(value) -> datetime | None:
    """An aware datetime; a time without a zone is taken as UTC."""
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


class Stats:
    def __init__(self) -> None:
        self.sessions: set[str] = set()
        self.main_in = self.main_out = self.main_cached = self.main_written = 0
        self.models: Counter = Counter()
        self.agents: dict[str, dict] = {}
        self.tool_calls: Counter = Counter()
        self.tool_chars: Counter = Counter()
        self.big: list[tuple[int, str, str]] = []
        self.polls = 0
        self.compactions = 0
        self.skills: Counter = Counter()
        self.errors: Counter = Counter()


def read_transcript(path: Path, since: datetime, stats: Stats, agent: dict | None) -> None:
    with path.open(encoding="utf-8", errors="replace") as lines:
        _read_lines(lines, since, stats, agent, path)


def _read_lines(lines, since: datetime, stats: Stats, agent: dict | None, path: Path) -> None:
    names: dict[str, tuple[str, str]] = {}
    counted: set[str] = set()      # one API response is split over several lines that repeat its usage
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        when = parse_time(entry.get("timestamp"))
        if when is None or when < since:
            continue
        if entry.get("isCompactSummary"):
            stats.compactions += 1
        if entry.get("isApiErrorMessage") or isinstance(entry.get("error"), str):
            kind = entry.get("error")
            stats.errors[kind if isinstance(kind, str) and ERROR_KIND.match(kind) else "other"] += 1
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        blocks = [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
        if entry.get("type") == "assistant":
            response = message.get("id") or entry.get("requestId") or entry.get("uuid")
            usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
            if response not in counted:
                counted.add(response)
                model = message.get("model") if isinstance(message.get("model"), str) else "unknown"
                if agent is None:
                    stats.sessions.add(path.stem)
                    stats.main_in += tokens_in(usage)
                    stats.main_cached += number(usage.get("cache_read_input_tokens"))
                    stats.main_written += number(usage.get("cache_creation_input_tokens"))
                    stats.main_out += number(usage.get("output_tokens"))
                    if not model.startswith("<"):           # skip placeholders such as <synthetic>
                        stats.models[model] += 1
                else:
                    agent["in"] += tokens_in(usage)
                    agent["cached"] += number(usage.get("cache_read_input_tokens"))
                    agent["written"] += number(usage.get("cache_creation_input_tokens"))
                    agent["out"] += number(usage.get("output_tokens"))
                    if not model.startswith("<"):           # skip placeholders such as <synthetic>
                        agent["model"] = model
            for block in blocks:
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name") if isinstance(block.get("name"), str) else "?"
                tool_input = block.get("input") if isinstance(block.get("input"), dict) else {}
                head = ""
                if name == "Bash" and isinstance(tool_input.get("command"), str):
                    command = tool_input["command"]
                    head = command_head(command)
                    if is_poll(command):
                        stats.polls += 1
                if name == "Skill" and isinstance(tool_input.get("skill"), str):
                    stats.skills[tool_input["skill"]] += 1
                stats.tool_calls[name] += 1
                names[str(block.get("id", ""))] = (name, head)
        elif entry.get("type") == "user":
            texts = [content] if isinstance(content, str) else [b.get("text") for b in blocks]
            for text in texts:
                if isinstance(text, str) and "<command-name>" in text:
                    stats.skills.update("/" + m.group(1) for m in SLASH.finditer(text))
            for block in blocks:
                if block.get("type") != "tool_result":
                    continue
                name, head = names.get(str(block.get("tool_use_id", "")), ("?", ""))
                size = result_chars(block.get("content"))
                stats.tool_chars[name] += size
                stats.big.append((size, name, head))


def collect(projects: Path, since: datetime) -> Stats:
    stats = Stats()
    for project in sorted(p for p in projects.iterdir() if p.is_dir()):
        for session in sorted(project.glob("*.jsonl")):
            read_transcript(session, since, stats, None)
            for sub in sorted((project / session.stem / "subagents").glob("agent-*.jsonl")):
                meta_path = sub.with_suffix(".meta.json")
                description = ""
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text())
                        if isinstance(meta, dict) and isinstance(meta.get("description"), str):
                            description = clean(meta["description"])
                    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                        pass
                agent = {"in": 0, "out": 0, "cached": 0, "written": 0, "model": "", "description": description or sub.stem}
                read_transcript(sub, since, stats, agent)
                if agent["in"] or agent["out"]:
                    stats.agents[sub.stem] = agent
    return stats


def description_of(skill_md: Path) -> tuple[str, str]:
    """The name and description from a SKILL.md front matter (one-line values, quotes stripped)."""
    name, description = skill_md.parent.name, ""
    lines = skill_md.read_text(encoding="utf-8", errors="replace").splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            key, _, value = line.partition(":")
            value = value.strip().strip("'\"")
            if key == "name" and value:
                name = value
            elif key == "description":
                description = value
    return name, description


def skill_listing(skills: Path, context: int, target: int, top: int) -> dict | None:
    """What the installed skills' descriptions cost in Claude Code's skill listing."""
    if not skills.is_dir():
        return None
    sizes = dict(description_of(p) for p in sorted(skills.glob("*/SKILL.md")))
    sizes = {n: len(d) for n, d in sizes.items()}
    total = sum(len(n) + 4 + min(c, MAX_DESC) for n, c in sizes.items()) + max(0, len(sizes) - 1)
    over = sorted(((c, n) for n, c in sizes.items() if c > target), reverse=True)
    return {
        "skills": len(sizes),
        "listing_chars": total,
        "budget": int(context * CHARS_PER_TOKEN * LISTING_SHARE),
        "budget_1m": int(1_000_000 * CHARS_PER_TOKEN * LISTING_SHARE),
        "desc_target": target,
        "over_target": len(over),
        "longest": [{"skill": n, "chars": c} for c, n in over[:top]],
    }


def report(stats: Stats, since: datetime, top: int, listing: dict | None = None) -> dict:
    agents = sorted(stats.agents.values(), key=lambda a: a["in"] + a["out"], reverse=True)
    agent_total = sum(a["in"] + a["out"] for a in agents)
    main_total = stats.main_in + stats.main_out
    everything = main_total + agent_total
    repeats = Counter(stats.big)          # the same tool, command and size again: often a re-read
    return {
        "since": since.isoformat(timespec="minutes"),
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sessions": len(stats.sessions),
        "main_tokens": main_total,
        "agent_tokens": agent_total,
        "agents": len(agents),
        "agent_share": round(agent_total / everything, 3) if everything else 0,
        "cache_reads": stats.main_cached + sum(a["cached"] for a in agents),
        "cache_writes": stats.main_written + sum(a["written"] for a in agents),
        "output_tokens": stats.main_out + sum(a["out"] for a in agents),
        "top_agents": [{"description": a["description"], "tokens": a["in"] + a["out"], "model": a["model"]}
                       for a in agents[:top]],
        "models": dict(stats.models.most_common()),
        "tool_calls": dict(stats.tool_calls.most_common()),
        "tool_result_chars": dict(stats.tool_chars.most_common(top)),
        "largest_results": [{"chars": c, "tool": n, "command": h, "times": k}
                            for (c, n, h), k in sorted(repeats.items(), reverse=True)[:top]],
        "polling_commands": stats.polls,
        "compactions": stats.compactions,
        "api_errors": dict(stats.errors.most_common()),
        "skills": dict(stats.skills.most_common()),
        "skill_listing": listing,
    }


def markdown(r: dict) -> str:
    errors = ", ".join(f"{k} {n}" for k, n in r["api_errors"].items()) or "none"
    out = [f"# Token usage since {r['since']}", "", f"Generated {r['generated']}.", "",
           f"- Sessions: {r['sessions']}; compactions: {r['compactions']}; API errors: {errors}",
           f"- Main conversation: {r['main_tokens']:,} tokens; background agents: {r['agent_tokens']:,} "
           f"in {r['agents']} agents ({r['agent_share']:.0%} of all)",
           f"- Of all tokens: {r['cache_reads']:,} were cache reads (cheaper), {r['cache_writes']:,} cache writes "
           f"and {r['output_tokens']:,} output",
           f"- Polling commands (sleeps, checks calls without --watch): {r['polling_commands']}", "",
           "## Agents that used the most", "", "| Agent | Tokens | Model |", "|---|---|---|"]
    out += [f"| {a['description']} | {a['tokens']:,} | {a['model']} |" for a in r["top_agents"]]
    out += ["", "## Tools by result size", "", "| Tool | Calls | Result characters |", "|---|---|---|"]
    out += [f"| {t} | {r['tool_calls'].get(t, 0)} | {c:,} |" for t, c in r["tool_result_chars"].items()]
    out += ["", "## Largest single results", "", "| Characters | Tool | Command | Times |", "|---|---|---|---|"]
    out += [f"| {b['chars']:,} | {b['tool']} | {b['command']} | {b['times']} |" for b in r["largest_results"]]
    out += ["", "## Skills and slash commands used", ""]
    out += [f"- {s}: {n}" for s, n in r["skills"].items()] or ["- none"]
    s = r["skill_listing"]
    if s:
        out += ["", "## Skill listing", "",
                f"- {s['skills']} skills take {s['listing_chars']:,} characters of the listing; the budget is "
                f"{s['budget']:,} at this context size ({s['budget_1m']:,} at 1M), shared with built-in and plugin skills",
                f"- Descriptions over {s['desc_target']} characters: {s['over_target']}"]
        out += [f"  - {d['skill']}: {d['chars']:,}" for d in s["longest"]]
    return "\n".join(out) + "\n"


def since_from(args) -> datetime:
    if args.since:
        when = parse_time(args.since)
        if when is None:
            raise SystemExit("--since must be an ISO date or time, for example 2026-11-11 or 2026-11-11T10:00+00:00")
        return when
    return datetime.now(timezone.utc) - timedelta(days=args.days)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--projects", default=str(Path.home() / ".claude" / "projects"))
    parser.add_argument("--since", help="ISO date or time (a time without a zone is UTC); default --days ago")
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skills", default=str(Path.home() / ".claude" / "skills"),
                        help="skills folder whose descriptions are measured against the listing budget")
    parser.add_argument("--context", type=int, default=200_000, help="context window in tokens")
    parser.add_argument("--desc-target", type=int, default=400, help="description length to flag above")
    args = parser.parse_args(argv)
    since = since_from(args)
    projects = Path(args.projects)
    if not projects.is_dir():
        print(f"No transcripts folder at {projects}", file=sys.stderr)
        return 1
    listing = skill_listing(Path(args.skills), args.context, args.desc_target, args.top)
    r = report(collect(projects, since), since, args.top, listing)
    print(json.dumps(r, indent=2) if args.json else markdown(r), end="\n" if args.json else "")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
