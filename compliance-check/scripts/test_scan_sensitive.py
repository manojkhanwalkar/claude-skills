"""Unit tests for scan_sensitive.py. Run: python3 -I -m unittest discover -s <this dir>"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan_sensitive as s  # noqa: E402


def kinds(line, path="src/main/App.java"):
    return [h.kind for h in s.scan_line(path, 1, line)]


class LuhnAndPanTest(unittest.TestCase):
    def test_luhn(self):
        self.assertTrue(s.luhn_ok("4539148803436467"))
        self.assertFalse(s.luhn_ok("4539148803436468"))

    def test_real_looking_pan_with_separators(self):
        self.assertEqual(kinds('x = "4539 1488 0343 6467"'), ["pan"])
        self.assertEqual(kinds('x = "4539-1488-0343-6467"'), ["pan"])

    def test_known_test_pan(self):
        self.assertEqual(kinds('"4111111111111111"'), ["test-pan"])

    def test_non_card_numbers_ignored(self):
        self.assertEqual(kinds("long ts = 1699999999999L;"), [])      # no brand prefix / Luhn
        self.assertEqual(kinds('"0000000000000000"'), [])             # repeated digit
        self.assertEqual(kinds("v = 1.4539148803436467"), [])        # part of a decimal
        self.assertEqual(kinds('"12345678901234567890123"'), [])     # too long

    def test_pan_never_printed_in_full(self):
        hit = next(s.scan_line("a", 1, "4539148803436467"))
        self.assertNotIn("453914880343", hit.detail)
        self.assertTrue(hit.detail.endswith("6467"))


class SsnTest(unittest.TestCase):
    def test_valid_ssn(self):
        self.assertEqual(kinds('"234-56-7890"'), ["ssn"])

    def test_invalid_ranges_ignored(self):
        for v in ("000-12-3456", "666-12-3456", "912-34-5678", "234-00-5678", "234-56-0000"):
            self.assertEqual(kinds(v), [], v)

    def test_placeholder(self):
        self.assertEqual(kinds('"123-45-6789"'), ["example-ssn"])

    def test_not_part_of_longer_number(self):
        self.assertEqual(kinds("1234-56-78901"), [])


class FieldAndLogTest(unittest.TestCase):
    def test_sad_field(self):
        self.assertIn("sad", kinds("private String cvv;"))
        self.assertIn("sad", kinds("track2_data = x", "a.py"))
        self.assertIn("sad", kinds("String cardCvv;"))
        self.assertIn("sad", kinds("CARD_SECURITY_CODE = 1"))
        self.assertEqual(kinds("int cvvx; Correlation cid; pinCode"), [])

    def test_log_with_sensitive_name(self):
        self.assertEqual(kinds('log.info("ssn {}", user.getSsn());'), ["log-pii"])
        self.assertEqual(kinds('System.out.println(cardNumber);'), ["log-pii"])

    def test_log_without_sensitive_name(self):
        self.assertEqual(kinds('logger.debug("span ok {}", span);'), [])

    def test_long_line_truncated(self):
        self.assertEqual(kinds("a" * (s.MAX_LINE_CHARS + 10) + " 4539148803436467"), [])


class FileWalkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        os.makedirs(os.path.join(root, "src", "test"))
        os.makedirs(os.path.join(root, "node_modules"))
        with open(os.path.join(root, "src", "App.java"), "w") as f:
            f.write('String s = "234-56-7890";\n')
        with open(os.path.join(root, "src", "test", "AppTest.java"), "w") as f:
            f.write('String s = "234-56-7890";\n')
        with open(os.path.join(root, "node_modules", "x.js"), "w") as f:
            f.write('"234-56-7890"\n')
        with open(os.path.join(root, "blob.dat"), "wb") as f:
            f.write(b"\0" + b"234-56-7890")
        with open(os.path.join(root, "logo.png"), "w") as f:
            f.write("234-56-7890")
        self.root = root

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *args, stdin=None):
        out, err = io.StringIO(), io.StringIO()
        old = sys.stdin
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            with redirect_stdout(out), redirect_stderr(err):
                rc = s.main(list(args))
        finally:
            sys.stdin = old
        return rc, out.getvalue(), err.getvalue()

    def test_walk_skips_vendor_binary_and_tags_tests(self):
        rc, out, err = self.run_main(self.root)
        self.assertEqual(rc, 0)
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 2, out)
        self.assertTrue(any(l.endswith("[test]") and "AppTest.java" in l for l in lines))
        self.assertTrue(any("App.java" in l and not l.endswith("[test]") for l in lines))
        self.assertIn("# 2 lead(s)", err)

    def test_json_and_files_from_stdin(self):
        path = os.path.join(self.root, "src", "App.java")
        rc, out, _ = self.run_main("--json", "--files-from", "-", stdin=path + "\n\n")
        rec = json.loads(out.strip())
        self.assertEqual(rec["kind"], "ssn")
        self.assertFalse(rec["in_test"])

    def test_missing_file_is_ignored(self):
        rc, out, _ = self.run_main(os.path.join(self.root, "nope.txt"))
        self.assertEqual((rc, out), (0, ""))

    def test_test_path_patterns(self):
        for p in ("src/test/java/A.java", "tests/a.py", "a/FooTest.java", "a/foo.spec.ts", "a/test_foo.py", "a/foo_test.go"):
            self.assertTrue(s.TEST_PATH.search(p), p)
        for p in ("src/main/java/A.java", "app/contest.py", "latest/x.js"):
            self.assertFalse(s.TEST_PATH.search(p), p)


if __name__ == "__main__":
    unittest.main()
