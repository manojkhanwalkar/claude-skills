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
MARKER = "zz-transcript-marker-QX7"        # stands for any transcript text; must never be printed
USAGE = {"input_tokens": 10, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 1000,
         "output_tokens": 50}


def assistant(ts, tool_uses=(), usage=None, model="claude-opus-5-5", msg_id=None):
    return {"type": "assistant", "timestamp": ts, "message": {
        "id": msg_id, "model": model, "usage": usage or USAGE,
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
            # One API response split over two lines that repeat its usage: counted once.
            assistant(NOW, [("t1", "Bash", {"command": f"mvn -B verify {MARKER}"})], msg_id="m1"),
            assistant(NOW, [("t2", "Bash", {"command": "sleep 60; gh pr checks 3"}),
                            ("t3", "Skill", {"skill": "pr-review"}),
                            ("t4", "Read", {"file_path": "/x"}),
                            ("t6", "Bash", {"command": "gh pr view 3"}),
                            ("t7", "Bash", {"command": "gh pr checks 3 --watch"}),
                            ("t8", "Bash", {"command": f"echo {MARKER}"}),
                            ("t10", "Bash", "not a dict input")], msg_id="m1"),
            result(NOW, "t1", "x" * 5000 + MARKER),
            result(NOW, "t2", [{"type": "text", "text": "y" * 300}, "stray"]),
            result(NOW, "t4", "z" * 20),
            {"type": "user", "timestamp": NOW, "message": {"content": [
                {"type": "text", "text": MARKER}, "not a block"]}},
            {"type": "user", "timestamp": NOW, "isCompactSummary": True, "message": {"content": "summary"}},
            {"type": "user", "timestamp": NOW, "message": "a string message"},
            assistant(OLD, [("t9", "Bash", {"command": "old"})], msg_id="m0"),      # before --since
            assistant("2026-11-20T12:00:00", msg_id="m2",                        # no zone: UTC, in range
                      usage={"input_tokens": "x" + MARKER, "output_tokens": True}),
            ["a", "list"], 42, {"type": "assistant", "timestamp": 12345},
            "not json",
        ]
        (project / "s1.jsonl").write_text("\n".join(l if isinstance(l, str) else json.dumps(l) for l in lines))
        sub = project / "s1" / "subagents" / "agent-a1.jsonl"
        sub.write_text(json.dumps(assistant(NOW, [("t5", "Grep", {"pattern": "p"})], model="claude-sonnet-5-5",
                                            usage={"input_tokens": 5, "output_tokens": 7}, msg_id="s1")) + "\n"
                       + json.dumps(result(NOW, "t5", "g" * 40)))
        sub.with_suffix(".meta.json").write_text(json.dumps({"description": "Review | PR\n7"}))
        (project / "s1" / "subagents" / "agent-a2.jsonl").write_text(json.dumps(assistant(OLD, msg_id="o")))
        (project / "s1" / "subagents" / "agent-a3.jsonl").write_text(
            json.dumps(assistant(NOW, msg_id="a3")) + "\n" + json.dumps(assistant(NOW, model="<synthetic>", msg_id="a3b")))
        (project / "s1" / "subagents" / "agent-a3.meta.json").write_text("{broken")
        self.since = datetime(2026, 11, 11, tzinfo=timezone.utc)

    def tearDown(self):
        self._tmp.cleanup()

    def run_report(self):
        return u.report(u.collect(self.root, self.since), self.since, 10)

    def test_totals_count_each_response_once(self):
        r = self.run_report()
        self.assertEqual(1, r["sessions"])
        self.assertEqual(1160, r["main_tokens"])                 # m1 once; m2's bad numbers count as 0
        self.assertEqual({"claude-opus-5-5": 2}, r["models"])   # m1 and m2, one each
        self.assertEqual(2, r["agents"])
        self.assertEqual({"description": "agent-a3", "tokens": 2320, "model": "claude-opus-5-5"}, r["top_agents"][0])
        self.assertEqual({"description": "Review PR 7", "tokens": 12, "model": "claude-sonnet-5-5"}, r["top_agents"][1])
        self.assertEqual(1000 + 2000, r["cache_reads"])
        self.assertEqual(50 + 7 + 100, r["output_tokens"])

    def test_tools_polling_skills_and_compactions(self):
        r = self.run_report()
        self.assertEqual(6, r["tool_calls"]["Bash"])
        self.assertEqual(5000 + len(MARKER) + 300, r["tool_result_chars"]["Bash"])
        self.assertEqual(40, r["tool_result_chars"]["Grep"])
        self.assertEqual({"pr-review": 1}, r["skills"])
        self.assertEqual(1, r["polling_commands"])     # the sleep only: not `gh pr view`, not a lone --watch
        self.assertEqual(1, r["compactions"])
        self.assertEqual({"chars": 5000 + len(MARKER), "tool": "Bash", "command": "mvn"}, r["largest_results"][0])

    def test_nothing_from_a_transcript_is_printed(self):
        r = self.run_report()
        out = u.markdown(r) + json.dumps(r)
        self.assertNotIn(MARKER, out)
        self.assertNotIn("xxxxx", out)
        self.assertNotIn("summary", out.lower())

    def test_command_head(self):
        self.assertEqual("gh pr", u.command_head("gh pr checks 3"))
        self.assertEqual("python3", u.command_head("/usr/bin/python3 -I x.py"))
        self.assertEqual("echo", u.command_head("echo ghp_" + "a1" * 18))       # a secret as the 2nd word
        self.assertEqual("mysql", u.command_head("mysql -pHunter2Secret"))
        self.assertEqual("git", u.command_head("git ghp1secretvalue"))            # not a plain subcommand
        self.assertEqual("git", u.command_head("git hunter-secret"))              # not a known subcommand
        self.assertEqual("git status", u.command_head("git status --short"))
        self.assertEqual("(command)", u.command_head("$(cat secret) | sh"))
        self.assertEqual("(command)", u.command_head("   "))

    def test_polling(self):
        self.assertTrue(u.is_poll("sleep 30"))
        self.assertTrue(u.is_poll("gh pr checks 3"))
        self.assertFalse(u.is_poll("gh pr checks 3 --watch"))
        self.assertFalse(u.is_poll("gh pr view 3"))
        self.assertFalse(u.is_poll("gh run watch 42"))
        self.assertFalse(u.is_poll("grep sleep notes.txt"))
        self.assertTrue(u.is_poll("make && sleep 5"))

    def test_helpers(self):
        self.assertEqual(0, u.result_chars(None))
        self.assertIsNone(u.parse_time("not a date"))
        self.assertIsNone(u.parse_time(None))
        self.assertEqual(timezone.utc, u.parse_time("2026-11-20T10:00:00").tzinfo)
        self.assertEqual(0, u.report(u.Stats(), self.since, 5)["agent_share"])
        self.assertEqual(0, u.number("12"))
        self.assertEqual("a b", u.clean("a |\n b"))

    def test_main_prints_markdown_or_json(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, u.main(["--projects", str(self.root), "--since", "2026-11-11"]))
        self.assertIn("# Token usage since 2026-11-11T00:00+00:00", out.getvalue())
        self.assertIn("| Review PR 7 | 12 | claude-sonnet-5-5 |", out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, u.main(["--projects", str(self.root), "--since", "2026-09-01T00:00+05:00", "--json"]))
        data = json.loads(out.getvalue())
        self.assertEqual("2026-09-01T00:00+05:00", data["since"])            # the offset is kept
        self.assertEqual(1160 * 2, data["main_tokens"])                       # the old response is in range now
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, u.main(["--projects", str(self.root), "--days", "1"]))

    def test_bad_since_and_missing_folder(self):
        with self.assertRaises(SystemExit):
            u.main(["--projects", str(self.root), "--since", "yesterday"])
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(1, u.main(["--projects", str(self.root / "nope")]))
        self.assertIn("No transcripts folder", err.getvalue())

    def test_no_skills_line(self):
        self.assertIn("- none", u.markdown(u.report(u.Stats(), self.since, 5)))


if __name__ == "__main__":
    unittest.main()
