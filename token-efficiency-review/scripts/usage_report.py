#!/usr/bin/env python3
"""Summarise where Claude Code spent tokens, from the local session transcripts.

Reads ~/.claude/projects/<project>/<session>.jsonl (the main conversation) and
<session>/subagents/agent-<id>.jsonl (background agents), keeps the messages since a date, and
prints a Markdown report (or JSON with --json): token totals, the agents that used the most, the
tools whose results took the most context, the largest single results, CI/status polling, context
compactions and the skills used.

Privacy: it prints numbers, tool and skill names, agent descriptions and at most the first two
words of a shell command (letters, digits and ./_- only). It never prints prompts, file contents,
command output or anything else from a transcript.

Usage: usage_report.py [--projects DIR] [--since YYYY-MM-DD] [--days N] [--top N] [--json]
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

POLL = re.compile(r"\bsleep\b|gh (pr|run) (checks|watch|view)|--watch\b")
SAFE_WORD = re.compile(r"^[A-Za-z0-9._/-]{1,40}$")


def tokens_in(usage: dict) -> int:
    """Input tokens of one API call, cached or not."""
    return sum(int(usage.get(k) or 0) for k in
               ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))


def cache_reads(usage: dict) -> int:
    """The part of the input read from the prompt cache (much cheaper than fresh input)."""
    return int(usage.get("cache_read_input_tokens") or 0)


def command_head(command: str) -> str:
    """At most the first two words of a shell command, and only safe-looking words."""
    words = [w for w in command.split()[:2] if SAFE_WORD.match(w)]
    return " ".join(words) or "(command)"


def result_chars(content) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(c.get("text", "")) for c in content if isinstance(c, dict))
    return 0


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class Stats:
    def __init__(self) -> None:
        self.sessions: set[str] = set()
        self.main_in = self.main_out = self.main_cached = 0
        self.models: Counter = Counter()
        self.agents: dict[str, dict] = {}
        self.tool_calls: Counter = Counter()
        self.tool_chars: Counter = Counter()
        self.big: list[tuple[int, str, str]] = []
        self.polls = 0
        self.compactions = 0
        self.skills: Counter = Counter()


def read_transcript(path: Path, since: datetime, stats: Stats, agent: dict | None) -> None:
    names: dict[str, tuple[str, str]] = {}
    for line in path.open(encoding="utf-8", errors="replace"):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        when = parse_time(entry.get("timestamp"))
        if when is None or when < since:
            continue
        if entry.get("isCompactSummary"):
            stats.compactions += 1
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        if entry.get("type") == "assistant":
            usage = message.get("usage") or {}
            model = message.get("model") or "unknown"
            if agent is None:
                stats.sessions.add(path.stem)
                stats.main_in += tokens_in(usage)
                stats.main_cached += cache_reads(usage)
                stats.main_out += int(usage.get("output_tokens") or 0)
                stats.models[model] += 1
            else:
                agent["in"] += tokens_in(usage)
                agent["cached"] += cache_reads(usage)
                agent["out"] += int(usage.get("output_tokens") or 0)
                if not model.startswith("<"):           # skip placeholders such as <synthetic>
                    agent["model"] = model
            for block in message.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = block.get("name", "?")
                tool_input = block.get("input") or {}
                head = ""
                if name == "Bash":
                    command = str(tool_input.get("command", ""))
                    head = command_head(command)
                    if POLL.search(command):
                        stats.polls += 1
                if name == "Skill":
                    stats.skills[str(tool_input.get("skill", "?"))] += 1
                stats.tool_calls[name] += 1
                names[block.get("id", "")] = (name, head)
        elif entry.get("type") == "user":
            for block in message.get("content") or [] if isinstance(message.get("content"), list) else []:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                name, head = names.get(block.get("tool_use_id", ""), ("?", ""))
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
                        description = str(json.loads(meta_path.read_text()).get("description", ""))[:60]
                    except (json.JSONDecodeError, OSError):
                        pass
                agent = {"in": 0, "out": 0, "cached": 0, "model": "", "description": description or sub.stem}
                read_transcript(sub, since, stats, agent)
                if agent["in"] or agent["out"]:
                    stats.agents[sub.stem] = agent
    return stats


def report(stats: Stats, since: datetime, top: int) -> dict:
    agents = sorted(stats.agents.values(), key=lambda a: a["in"] + a["out"], reverse=True)
    agent_total = sum(a["in"] + a["out"] for a in agents)
    main_total = stats.main_in + stats.main_out
    return {
        "since": since.date().isoformat(),
        "sessions": len(stats.sessions),
        "main_tokens": main_total,
        "agent_tokens": agent_total,
        "agents": len(agents),
        "cache_reads": stats.main_cached + sum(a["cached"] for a in agents),
        "output_tokens": stats.main_out + sum(a["out"] for a in agents),
        "agent_share": round(agent_total / (main_total + agent_total), 3) if main_total + agent_total else 0,
        "top_agents": [{"description": a["description"], "tokens": a["in"] + a["out"], "model": a["model"]}
                       for a in agents[:top]],
        "models": dict(stats.models.most_common()),
        "tool_calls": dict(stats.tool_calls.most_common()),
        "tool_result_chars": dict(stats.tool_chars.most_common(top)),
        "largest_results": [{"chars": c, "tool": n, "command": h}
                            for c, n, h in sorted(stats.big, reverse=True)[:top]],
        "polling_commands": stats.polls,
        "compactions": stats.compactions,
        "skills": dict(stats.skills.most_common()),
    }


def markdown(r: dict) -> str:
    out = [f"# Token usage since {r['since']}", "",
           f"- Sessions: {r['sessions']}; compactions: {r['compactions']}",
           f"- Main conversation: {r['main_tokens']:,} tokens; background agents: {r['agent_tokens']:,} "
           f"in {r['agents']} agents ({r['agent_share']:.0%} of all)",
           f"- Of all tokens: {r['cache_reads']:,} were cache reads (cheaper) and {r['output_tokens']:,} output",
           f"- Polling commands (sleep, gh pr checks, --watch): {r['polling_commands']}", "",
           "## Agents that used the most", "", "| Agent | Tokens | Model |", "|---|---|---|"]
    out += [f"| {a['description']} | {a['tokens']:,} | {a['model']} |" for a in r["top_agents"]]
    out += ["", "## Tools by result size", "", "| Tool | Calls | Result characters |", "|---|---|---|"]
    out += [f"| {t} | {r['tool_calls'].get(t, 0)} | {c:,} |" for t, c in r["tool_result_chars"].items()]
    out += ["", "## Largest single results", "", "| Characters | Tool | Command |", "|---|---|---|"]
    out += [f"| {b['chars']:,} | {b['tool']} | {b['command']} |" for b in r["largest_results"]]
    out += ["", "## Skills used", ""]
    out += [f"- {s}: {n}" for s, n in r["skills"].items()] or ["- none"]
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--projects", default=str(Path.home() / ".claude" / "projects"))
    parser.add_argument("--since", help="YYYY-MM-DD (default: --days ago)")
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    since = (datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc) if args.since
             else datetime.now(timezone.utc) - timedelta(days=args.days))
    projects = Path(args.projects)
    if not projects.is_dir():
        print(f"No transcripts folder at {projects}", file=sys.stderr)
        return 1
    r = report(collect(projects, since), since, args.top)
    print(json.dumps(r, indent=2) if args.json else markdown(r), end="" if not args.json else "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
