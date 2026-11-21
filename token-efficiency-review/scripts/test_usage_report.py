"""Tests for usage_report.py, on synthetic transcripts (no real session data)."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

import usage_report as u

NOW = "2026-11-21T12:00:00Z"
OLD = "2026-10-01T12:00:00Z"
SECRET = "sk-live-should-never-appear-0123456789"


def assistant(ts, tool_uses=(), usage=None, model="claude-opus-5-5"):
    return {"type": "assistant", "timestamp": ts, "message": {
        "model": model,
        "usage": usage or {"input_tokens": 10, "cache_creation_input_tokens": 100,
                           "cache_read_input_tokens": 1000, "output_tokens": 50},
        "content": [{"type": "tool_use", "id": i, "name": n, "input": inp} for i, n, inp in tool_uses]}}


def result(ts, tool_use_id, text):
    return {"type": "user", "timestamp": ts, "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_use_id, "content": text}]}}


class UsageReportTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        project = self.root / "-home-me-proj"
        (project / "s1" / "subagents").mkdir(parents=True)
        lines = [
            assistant(NOW, [("t1", "Bash", {"command": f"mvn -B verify {SECRET}"}),
                            ("t2", "Bash", {"command": "sleep 60; gh pr checks 3 --watch"}),
                            ("t3", "Skill", {"skill": "pr-review"}),
                            ("t4", "Read", {"file_path": "/x"})]),
            result(NOW, "t1", "x" * 5000 + SECRET),
            result(NOW, "t2", [{"type": "text", "text": "y" * 300}]),
            result(NOW, "t4", "z" * 20),
            {"type": "user", "timestamp": NOW, "isCompactSummary": True, "message": {"content": "summary"}},
            assistant(OLD, [("t9", "Bash", {"command": "old"})]),     # before --since: ignored
            "not json",
        ]
        (project / "s1.jsonl").write_text("\n".join(l if isinstance(l, str) else json.dumps(l) for l in lines))
        sub = project / "s1" / "subagents" / "agent-a1.jsonl"
        sub.write_text(json.dumps(assistant(NOW, [("t5", "Grep", {"pattern": "p"})], model="claude-sonnet-5-5",
                                            usage={"input_tokens": 5, "output_tokens": 7})) + "\n"
                       + json.dumps(result(NOW, "t5", "g" * 40)))
        sub.with_suffix(".meta.json").write_text(json.dumps({"description": "Review PR 7"}))
        empty = project / "s1" / "subagents" / "agent-a2.jsonl"
        empty.write_text(json.dumps(assistant(OLD)))                     # no usage in range: left out
        (project / "s1" / "subagents" / "agent-a3.jsonl").write_text(json.dumps(assistant(NOW)))
        (project / "s1" / "subagents" / "agent-a3.meta.json").write_text("{broken")
        self.since = datetime(2026, 11, 11, tzinfo=timezone.utc)

    def tearDown(self):
        self._tmp.cleanup()

    def run_report(self):
        return u.report(u.collect(self.root, self.since), self.since, 10)

    def test_totals_agents_tools_and_skills(self):
        r = self.run_report()
        self.assertEqual(1, r["sessions"])
        self.assertEqual(1110 + 50, r["main_tokens"])
        self.assertEqual(2, r["agents"])
        self.assertEqual({"description": "agent-a3", "tokens": 1160, "model": "claude-opus-5-5"}, r["top_agents"][0])
        self.assertEqual({"description": "Review PR 7", "tokens": 12, "model": "claude-sonnet-5-5"}, r["top_agents"][1])
        self.assertEqual(2, r["tool_calls"]["Bash"])
        self.assertEqual(5000 + len(SECRET) + 300, r["tool_result_chars"]["Bash"])
        self.assertEqual(40, r["tool_result_chars"]["Grep"])
        self.assertEqual({"pr-review": 1}, r["skills"])
        self.assertEqual(1, r["polling_commands"])
        self.assertEqual(1, r["compactions"])
        self.assertEqual(2000, r["cache_reads"])          # main 1000 + agent-a3 1000
        self.assertEqual(50 + 7 + 50, r["output_tokens"])
        self.assertEqual({"chars": 5000 + len(SECRET), "tool": "Bash", "command": "mvn -B"}, r["largest_results"][0])

    def test_nothing_from_a_transcript_is_printed(self):
        out = u.markdown(self.run_report()) + json.dumps(self.run_report())
        self.assertNotIn(SECRET, out)
        self.assertNotIn("xxxxx", out)
        self.assertNotIn("summary", out.lower().replace("# token usage", ""))

    def test_command_head_keeps_only_safe_words(self):
        self.assertEqual("gh pr", u.command_head("gh pr checks 3"))
        self.assertEqual("curl", u.command_head("curl -H'Authorization: x'"))
        self.assertEqual("(command)", u.command_head("$(cat secret) | sh"))
        self.assertEqual("(command)", u.command_head(""))

    def test_helpers(self):
        self.assertEqual(0, u.result_chars(None))
        self.assertIsNone(u.parse_time("not a date"))
        self.assertIsNone(u.parse_time(None))
        self.assertEqual(0, u.report(u.Stats(), self.since, 5)["agent_share"])

    def test_main_prints_markdown_or_json(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, u.main(["--projects", str(self.root), "--since", "2026-11-11"]))
        self.assertIn("# Token usage since 2026-11-11", out.getvalue())
        self.assertIn("| Review PR 7 | 12 | claude-sonnet-5-5 |", out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, u.main(["--projects", str(self.root), "--days", "100000", "--json"]))
        data = json.loads(out.getvalue())
        self.assertEqual(1, data["sessions"])
        self.assertEqual(1160 * 2, data["main_tokens"])   # the old turn is in range now

    def test_a_missing_folder_is_reported(self):
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(1, u.main(["--projects", str(self.root / "nope")]))
        self.assertIn("No transcripts folder", err.getvalue())

    def test_no_skills_line(self):
        r = u.report(u.Stats(), self.since, 5)
        self.assertIn("- none", u.markdown(r))


if __name__ == "__main__":
    unittest.main()
