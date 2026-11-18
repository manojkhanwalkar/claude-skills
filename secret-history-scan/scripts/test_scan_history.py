"""Tests for scan_history.py. Run: python3 -I -m unittest discover -s secret-history-scan/scripts -p 'test_*.py'

Fake secrets are assembled at run time, so this file itself holds nothing a secret scanner
(or GitHub push protection) would flag. Scanner output is captured, never shown.
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scan_history  # noqa: E402

KEY = b"k" * 32
FAKE_AWS = "AKIA" + "Q7XK2M4PZ8RT1VWB"  # 20 chars, AWS access key id shape
FAKE_AWS_2 = "AKIA" + "M3NB8VC2XZ5LK9JH"
FAKE_GH = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
FAKE_GENERIC = "Zt9#qL2v" + "Xw8!rP4kM7"  # random-looking, 18 chars
BEGIN = "-----BEGIN " + "RSA PRIVATE KEY-----"
END = "-----END " + "RSA PRIVATE KEY-----"
PGP_BEGIN = "-----BEGIN " + "PGP PRIVATE KEY BLOCK-----"


def git(repo, *args, env=None):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                   env={**os.environ, **(env or {})})


def key_file(body_seed: str) -> str:
    return "\n".join([BEGIN, "MIIEow" + body_seed * 8, "q9" + body_seed * 6, END, ""])


class ScanHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@example.invalid")
        git(self.repo, "config", "user.name", "Test")
        self.key_path = Path(self.tmp.name) / "scan.key"

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, path, text, message, env=None):
        (self.repo / path).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / path).write_text(text)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", message, env=env)
        return subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()

    def scan(self, **kw):
        return scan_history.scan(self.repo, KEY, **kw)

    def rules(self, **kw):
        return [f["rule"] for f in self.scan(**kw)]

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = scan_history.main([*args, "--key-file", str(self.key_path)])
        return code, out.getvalue(), err.getvalue()

    # --- basic detection -------------------------------------------------------------

    def test_finds_a_secret_that_was_deleted_later_and_never_prints_it(self):
        self.commit("config.py", f'AWS_KEY = "{FAKE_AWS}"\n', "add config")
        self.commit("config.py", "AWS_KEY = os.environ['AWS_KEY']\n", "remove key")
        (finding,) = self.scan()
        self.assertEqual(finding["rule"], "aws-access-key-id")
        self.assertFalse(finding["in_head"])
        self.assertEqual(finding["paths"], ["config.py"])
        self.assertEqual(finding["line"], 1)
        self.assertEqual(finding["masked"], "AKIA…(20 chars)")
        self.assertNotIn(FAKE_AWS, json.dumps(finding))

    def test_reports_the_commit_that_introduced_the_secret(self):
        first = self.commit("a.txt", f"token {FAKE_GH}\n", "first")
        self.commit("b.txt", f"again {FAKE_GH}\n", "second")
        (finding,) = self.scan()
        self.assertEqual(finding["first_commit"], first)
        self.assertEqual(sorted(finding["paths"]), ["a.txt", "b.txt"])
        self.assertTrue(finding["in_head"])

    def test_introducer_found_even_when_a_descendant_has_an_earlier_date(self):
        self.commit("readme.md", "hello\n", "init")
        introducer = self.commit("a.txt", f"{FAKE_AWS}\n", "introduce",
                                 env={"GIT_COMMITTER_DATE": "2030-01-01T00:00:00Z"})
        self.commit("b.txt", f"{FAKE_AWS}\n", "copy, clock behind",
                    env={"GIT_COMMITTER_DATE": "2001-01-01T00:00:00Z"})
        (finding,) = self.scan()
        self.assertEqual(finding["first_commit"], introducer)

    def test_scans_other_branches(self):
        self.commit("readme.md", "hello\n", "init")
        git(self.repo, "checkout", "-q", "-b", "feature")
        self.commit("key.pem", key_file("Ab"), "add key")
        git(self.repo, "checkout", "-q", "main")
        self.assertEqual(self.rules(), ["private-key"])

    def test_reflog_finds_a_commit_no_ref_reaches(self):
        self.commit("readme.md", "hello\n", "init")
        self.commit("k.txt", f"{FAKE_AWS}\n", "oops")
        git(self.repo, "reset", "-q", "--hard", "HEAD~1")
        self.assertEqual(self.scan(), [])
        self.assertEqual(self.rules(reflog=True), ["aws-access-key-id"])

    def test_same_secret_twice_in_one_file_is_listed_once(self):
        self.commit("a.txt", f"{FAKE_AWS}\n{FAKE_AWS}\n", "twice")
        (finding,) = self.scan()
        self.assertEqual(finding["paths"], ["a.txt"])

    # --- review regressions -----------------------------------------------------------

    def test_distinct_private_keys_get_distinct_fingerprints(self):
        self.commit("test/fixture.pem", key_file("Ab"), "fixture")
        self.commit("deploy/prod.pem", key_file("Zq"), "prod")
        findings = self.scan()
        self.assertEqual(len(findings), 2)
        fixture = next(f for f in findings if f["paths"] == ["test/fixture.pem"])
        remaining = self.scan(allowed=frozenset({fixture["fingerprint"]}))
        self.assertEqual([f["paths"] for f in remaining], [["deploy/prod.pem"]])
        self.assertTrue(fixture["masked"].startswith("[RSA PRIVATE KEY block, "))

    def test_pgp_private_key_block(self):
        self.commit("k.asc", f"{PGP_BEGIN}\nlQOYBF\n-----END PGP PRIVATE KEY BLOCK-----\n", "pgp")
        self.assertEqual(self.rules(), ["private-key"])

    def test_secret_added_in_a_merge_resolution(self):
        self.commit("a.txt", "base\n", "base")
        git(self.repo, "checkout", "-q", "-b", "side")
        self.commit("a.txt", "side\n", "side")
        git(self.repo, "checkout", "-q", "main")
        self.commit("a.txt", "main\n", "main")
        subprocess.run(["git", "-C", str(self.repo), "merge", "-q", "side"], capture_output=True)
        (self.repo / "a.txt").write_text("resolved\n")
        (self.repo / "creds.txt").write_text(f"{FAKE_AWS}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "--no-edit")
        self.assertEqual(self.rules(), ["aws-access-key-id"])

    def test_quoted_and_spaced_paths(self):
        self.commit("café.txt", f"{FAKE_AWS}\n", "accent")
        self.commit('q"x.txt', f"{FAKE_GH}\n", "quote")
        self.commit("x y.txt", f"{FAKE_AWS_2}\n", "space")
        found = {f["paths"][0]: f for f in self.scan()}
        self.assertEqual(set(found), {"café.txt", 'q"x.txt', "x y.txt"})
        self.assertTrue(all(f["in_head"] for f in found.values()))

    def test_an_added_line_that_looks_like_a_header_cannot_hide_a_secret(self):
        self.commit("a.txt", f"++ b/evil\n{FAKE_AWS}\n", "sneaky")
        (finding,) = self.scan()
        self.assertEqual(finding["paths"], ["a.txt"])
        self.assertEqual(finding["line"], 2)

    def test_generic_assignment_forms(self):
        lines = [f'db_password = "{FAKE_GENERIC}"', f'CLIENT_SECRET="{FAKE_GENERIC}x"',
                 f'"password": "{FAKE_GENERIC}y"', f"password: {FAKE_GENERIC}z",
                 f"aws_secret_access_key = {FAKE_GENERIC}w"]
        self.commit("s.txt", "\n".join(lines) + "\n", "forms")
        findings = self.scan()
        self.assertEqual([f["rule"] for f in findings], ["generic-secret-assignment"] * 5)
        self.assertTrue(all(f["masked"].startswith("…(") for f in findings))

    def test_generic_assignment_ignores_placeholders_and_low_entropy(self):
        self.commit("s.py", 'password = "changeme-please-123"\napi_key = "aaaaaaaaaaaaaaaa"\n'
                    'token = "${GITHUB_TOKEN_VALUE}"\n', "placeholders")
        self.assertEqual(self.scan(), [])

    def test_a_key_matching_two_rules_is_reported_once(self):
        anthropic = "sk-ant-" + "api03-" + "Q9x" * 14
        self.commit("a.txt", f"key {anthropic}\n", "anthropic")
        self.assertEqual(self.rules(), ["anthropic-api-key"])

    def test_a_token_inside_a_generic_value_is_reported_as_the_token_only(self):
        self.commit("a.env", f"secret=xx-{FAKE_GH}\n", "embedded")
        self.assertEqual(self.rules(), ["github-token"])

    def test_file_without_a_trailing_newline(self):
        self.commit("a.txt", f"{FAKE_AWS}", "no newline")
        self.commit("a.txt", f"{FAKE_AWS}\n{FAKE_AWS_2}", "still no newline")
        self.assertEqual(self.rules(), ["aws-access-key-id", "aws-access-key-id"])

    def test_unterminated_key_blocks_are_still_reported(self):
        (self.repo / "half.pem").write_text(f"{BEGIN}\nMIIEowAbAbAb\n")
        (self.repo / "z.txt").write_text(f"{FAKE_AWS}\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "key cut short, then another file")
        self.commit("last.pem", f"{BEGIN}\nMIIEowZqZqZq\n", "key cut short at the end")
        self.assertEqual(sorted(self.rules()), ["aws-access-key-id", "private-key", "private-key"])

    def test_one_line_key_is_masked_and_other_secrets_on_the_hunk_still_found(self):
        body = "MIIEow" + "Kq7Zp3" * 10
        one_line = BEGIN + "\\n" + body + "\\n" + END
        token = "Zt9qL2vXw8rP4kM7" + "aQ"
        self.commit("sa.json", '{\n  "private_key": "' + one_line + '",\n  "token": "' + token + '"\n}\n', "gcp")
        findings = self.scan()
        self.assertEqual(sorted(f["rule"] for f in findings), ["generic-secret-assignment", "private-key"])
        dumped = json.dumps(findings)
        self.assertNotIn(body, dumped)
        self.assertNotIn(token, dumped)

    def test_a_key_header_in_prose_does_not_swallow_the_hunk(self):
        self.commit("README.md", f"Never commit a {BEGIN} file.\nExample: see docs.\nkey {FAKE_AWS}\n", "docs")
        self.assertIn("aws-access-key-id", self.rules())

    def test_lines_after_a_stray_key_header_are_still_scanned(self):
        self.commit("notes.txt", f"Format: {BEGIN}\n{FAKE_AWS}\n", "bare key after header")
        self.commit("c.yml", f"note: {BEGIN}\npassword: {FAKE_GENERIC}\n", "yaml after header")
        self.assertEqual(sorted(self.rules()), ["aws-access-key-id", "generic-secret-assignment",
                                                "private-key", "private-key"])

    def test_non_ascii_names_with_quotes(self):
        self.commit('é"x.txt', f"{FAKE_AWS}\n", "latin")
        self.commit('日"x.txt', f"{FAKE_GH}\n", "cjk")
        found = {f["paths"][0]: f["in_head"] for f in self.scan()}
        self.assertEqual(found, {'é"x.txt': True, '日"x.txt': True})

    def test_a_malformed_quoted_path_is_kept_rather_than_aborting(self):
        self.assertEqual(scan_history.unquote_path('"b/bad\\x"'), "bad\\x")
        self.assertEqual(scan_history.unquote_path("b/x y.txt\t"), "x y.txt")

    def test_code_is_not_reported_as_a_secret(self):
        lines = ["token = self._extract_bearer_token(request)",
                 "password_hash = hashlib.sha256(raw).hexdigest()",
                 "apiKey: process.env.ANTHROPIC_API_KEY_VALUE",
                 "tokenizer = AutoTokenizer.from_pretrained(name_or_path)",
                 "max_tokens=self.config.maxTokensValue",
                 "pwd = Path.cwd().resolve().parent",
                 "self._tokens = min(self._capacity, refill)"]
        self.commit("code.py", "\n".join(lines) + "\n", "code")
        self.assertEqual(self.scan(), [])

    def test_short_values_show_no_prefix(self):
        self.assertEqual(scan_history.mask("slack-token", "xoxb-12345678"), "…(13 chars)")

    # --- context ----------------------------------------------------------------------

    def test_context_masks_secrets_and_key_material(self):
        sha = self.commit("a.txt", f"one\nkey = {FAKE_AWS}\n{key_file('Ab')}after\n", "ctx")
        code, out, _ = self.run_main(str(self.repo), "--context", f"{sha}:a.txt:2", "--radius", "4")
        self.assertEqual(code, 0)
        self.assertNotIn(FAKE_AWS, out)
        self.assertNotIn("MIIEow", out)
        self.assertIn("AKIA…(20 chars)", out)
        self.assertIn("[private key material]", out)

    def test_context_masks_what_the_scanner_does_not_report(self):
        weak, url_pw = "hunter2hunter2", "s3cr3tP4ss"
        sha = self.commit("db.py", f'password = "{weak}"\nurl = "postgres://app:{url_pw}@db/main"\nname = "service"\n', "db")
        code, out, _ = self.run_main(str(self.repo), "--context", f"{sha}:db.py:2")
        self.assertEqual(code, 0)
        self.assertNotIn(weak, out)
        self.assertNotIn(url_pw, out)
        self.assertIn("service", out)

    def test_context_masks_short_and_spaced_passwords(self):
        lines = ['password = "hunter2"', 'DB_PASSWORD: "Summer2024"', '"password": "letmein!"',
                 'secret: "my secret phrase"', 'conn = connect("db", "admin", "P@ss!w0rd#123")',
                 'label = "service"']
        sha = self.commit("c.py", "\n".join(lines) + "\n", "short")
        code, out, _ = self.run_main(str(self.repo), "--context", f"{sha}:c.py:3", "--radius", "5")
        self.assertEqual(code, 0)
        for value in ["hunter2", "Summer2024", "letmein!", "my secret phrase", "P@ss!w0rd#123"]:
            self.assertNotIn(value, out)
        self.assertIn('"service"', out)

    def test_context_errors(self):
        self.commit("a.txt", "x\n", "init")
        self.assertEqual(self.run_main(str(self.repo), "--context", "nonsense")[0], 2)
        self.assertEqual(self.run_main(str(self.repo), "--context", "HEAD:missing.txt:1")[0], 2)

    # --- CLI and errors -----------------------------------------------------------------

    def test_main_writes_json_reads_an_allow_file_and_creates_a_private_key_file(self):
        self.commit("a.txt", f"{FAKE_AWS}\n{FAKE_GH}\n", "add")
        out = Path(self.tmp.name) / "out.json"
        code, _, _ = self.run_main(str(self.repo), "--out", str(out))
        self.assertEqual(code, 1)
        self.assertEqual(self.key_path.stat().st_mode & 0o777, 0o600)
        gh = next(f for f in json.loads(out.read_text()) if f["rule"] == "github-token")
        allow = Path(self.tmp.name) / "allow.txt"
        allow.write_text(f"# reviewed\n{gh['fingerprint']}  # test token\n\n")
        code, _, _ = self.run_main(str(self.repo), "--allow", str(allow), "--out", str(out))
        self.assertEqual([f["rule"] for f in json.loads(out.read_text())], ["aws-access-key-id"])
        self.assertNotIn(FAKE_AWS, out.read_text())

    def test_main_on_a_clean_history_returns_zero(self):
        self.commit("a.txt", "nothing secret here\n", "init")
        self.assertEqual(self.run_main(str(self.repo))[0], 0)

    def test_errors_exit_2(self):
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(self.run_main(other)[0], 2)
        self.commit("a.txt", "x\n", "init")
        self.assertEqual(self.run_main(str(self.repo), "--allow", "/no/such/file")[0], 2)

    def test_a_failing_git_log_is_an_error_not_a_clean_result(self):
        self.commit("a.txt", "x\n", "init")
        with self.assertRaises(scan_history.ScanError):
            list(scan_history.added_lines(self.repo / "missing-subdir", reflog=False))
        real = scan_history.added_lines

        def failing(repo, reflog):
            raise scan_history.ScanError("git log failed")
            yield  # pragma: no cover

        scan_history.added_lines = failing
        try:
            self.assertEqual(self.run_main(str(self.repo))[0], 2)
        finally:
            scan_history.added_lines = real

    def test_git_missing_is_an_error(self):
        real = scan_history.subprocess.run

        def no_git(*a, **k):
            raise FileNotFoundError("git")

        scan_history.subprocess.run = no_git
        try:
            self.assertEqual(self.run_main(str(self.repo))[0], 2)
        finally:
            scan_history.subprocess.run = real
        real_popen = scan_history.subprocess.Popen
        scan_history.subprocess.Popen = no_git
        try:
            with self.assertRaises(scan_history.ScanError):
                list(scan_history.added_lines(self.repo, reflog=False))
        finally:
            scan_history.subprocess.Popen = real_popen

    def test_cli_exit_codes_and_output(self):
        script = Path(scan_history.__file__)
        cmd = [sys.executable, "-I", str(script), str(self.repo), "--key-file", str(self.key_path)]
        self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
        self.commit("a.txt", f"{FAKE_AWS}\n", "add")
        found = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(found.returncode, 1)
        self.assertNotIn(FAKE_AWS, found.stdout + found.stderr)


if __name__ == "__main__":
    unittest.main()
