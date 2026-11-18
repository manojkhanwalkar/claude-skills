"""Tests for scan_history.py. Run: python3 -I -m unittest discover -s secret-history-scan/scripts -p 'test_*.py'

Fake secrets are assembled at run time, so this file itself holds nothing a secret scanner
(or GitHub push protection) would flag.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scan_history  # noqa: E402

FAKE_AWS = "AKIA" + "Q7XK2M4PZ8RT1VWB"  # 20 chars, AWS access key id shape
FAKE_GH = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
FAKE_GENERIC = "Zt9#qL2v" + "Xw8!rP4kM7"  # random-looking, 18 chars
KEY_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class ScanHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@example.invalid")
        git(self.repo, "config", "user.name", "Test")

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, path, text, message):
        (self.repo / path).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / path).write_text(text)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", message)

    def test_finds_a_secret_that_was_deleted_later_and_never_prints_it(self):
        self.commit("config.py", f'AWS_KEY = "{FAKE_AWS}"\n', "add config")
        self.commit("config.py", "AWS_KEY = os.environ['AWS_KEY']\n", "remove key")
        findings = scan_history.scan(self.repo)
        self.assertEqual([f["rule"] for f in findings], ["aws-access-key-id"])
        finding = findings[0]
        self.assertFalse(finding["in_head"])
        self.assertEqual(finding["paths"], ["config.py"])
        self.assertEqual(finding["masked"], "AKIA…(20 chars)")
        self.assertNotIn(FAKE_AWS, json.dumps(findings))

    def test_reports_the_commit_that_introduced_the_secret(self):
        self.commit("a.txt", f"token {FAKE_GH}\n", "first")
        first = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"],
                               capture_output=True, text=True, check=True).stdout.strip()
        self.commit("b.txt", f"again {FAKE_GH}\n", "second")
        (finding,) = scan_history.scan(self.repo)
        self.assertEqual(finding["first_commit"], first)
        self.assertEqual(sorted(finding["paths"]), ["a.txt", "b.txt"])
        self.assertTrue(finding["in_head"])

    def test_scans_other_branches(self):
        self.commit("readme.md", "hello\n", "init")
        git(self.repo, "checkout", "-q", "-b", "feature")
        self.commit("key.pem", KEY_HEADER + "\nabc\n", "add key")
        git(self.repo, "checkout", "-q", "main")
        rules = [f["rule"] for f in scan_history.scan(self.repo)]
        self.assertEqual(rules, ["private-key"])

    def test_generic_assignment_needs_a_random_looking_value(self):
        self.commit("s.py", f'password = "{FAKE_GENERIC}"\npassword = "changeme-please-123"\n'
                    'api_key = "aaaaaaaaaaaaaaaa"\n', "secrets")
        findings = scan_history.scan(self.repo)
        self.assertEqual([f["rule"] for f in findings], ["generic-secret-assignment"])

    def test_allow_list_skips_fingerprints(self):
        self.commit("a.txt", f"{FAKE_AWS}\n", "add")
        allowed = frozenset({scan_history.fingerprint(FAKE_AWS)})
        self.assertEqual(scan_history.scan(self.repo, allowed=allowed), [])

    def test_cli_exit_codes_and_output(self):
        script = Path(scan_history.__file__)
        clean = subprocess.run([sys.executable, "-I", str(script), str(self.repo)],
                               capture_output=True, text=True)
        self.assertEqual(clean.returncode, 0)  # empty repo: no commits, no findings
        self.commit("a.txt", f"{FAKE_AWS}\n", "add")
        found = subprocess.run([sys.executable, "-I", str(script), str(self.repo)],
                               capture_output=True, text=True)
        self.assertEqual(found.returncode, 1)
        self.assertNotIn(FAKE_AWS, found.stdout + found.stderr)
        bad = subprocess.run([sys.executable, "-I", str(script), self.tmp.name + "/nope"],
                             capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)

    def test_main_in_process_writes_json_and_reads_an_allow_file(self):
        self.commit("a.txt", f"{FAKE_AWS}\n{FAKE_GH}\n", "add")
        out = self.repo / "out.json"
        allow = self.repo / "allow.txt"
        allow.write_text(f"# a reviewed false positive\n{scan_history.fingerprint(FAKE_GH)}  # test key\n\n")
        code = scan_history.main([str(self.repo), "--allow", str(allow), "--out", str(out)])
        self.assertEqual(code, 1)
        findings = json.loads(out.read_text())
        self.assertEqual([f["rule"] for f in findings], ["aws-access-key-id"])
        self.assertNotIn(FAKE_AWS, out.read_text())

    def test_main_without_out_on_a_clean_history_returns_zero(self):
        self.commit("a.txt", "nothing secret here\n", "init")
        self.assertEqual(scan_history.main([str(self.repo)]), 0)

    def test_main_rejects_a_directory_that_is_not_a_repository(self):
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(scan_history.main([other]), 2)

    def test_reflog_finds_a_commit_no_ref_reaches(self):
        self.commit("readme.md", "hello\n", "init")
        self.commit("k.txt", f"{FAKE_AWS}\n", "oops")
        git(self.repo, "reset", "-q", "--hard", "HEAD~1")
        self.assertEqual(scan_history.scan(self.repo), [])
        rules = [f["rule"] for f in scan_history.scan(self.repo, reflog=True)]
        self.assertEqual(rules, ["aws-access-key-id"])

    def test_same_secret_twice_in_one_file_is_listed_once(self):
        self.commit("a.txt", f"{FAKE_AWS}\n{FAKE_AWS}\n", "twice")
        (finding,) = scan_history.scan(self.repo)
        self.assertEqual(finding["paths"], ["a.txt"])

    def test_a_failing_git_log_is_an_error_not_a_clean_result(self):
        self.commit("a.txt", "x\n", "init")
        with self.assertRaises(RuntimeError):
            list(scan_history.history(self.repo / "missing-subdir", reflog=False))
        real_history = scan_history.history

        def failing(repo, reflog):
            raise RuntimeError("git log failed")
            yield  # pragma: no cover

        scan_history.history = failing
        try:
            self.assertEqual(scan_history.main([str(self.repo)]), 2)
        finally:
            scan_history.history = real_history


if __name__ == "__main__":
    unittest.main()
