"""Unit tests for scan_trackers.py. Run: python3 -I -m unittest discover -s <this dir> -p 'test_*.py'"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan_trackers as t  # noqa: E402


def hits(line, path="a.html"):
    return [(h.kind, h.detail) for h in t.scan_line(path, 1, line)]


class LineTest(unittest.TestCase):
    def test_third_party_script_without_sri(self):
        got = hits('<script src="https://cdn.example.com/x.js"></script>')
        self.assertIn(("third-party-script", "cdn.example.com"), got)
        self.assertIn(("no-sri", "cdn.example.com"), got)

    def test_third_party_script_with_sri(self):
        got = hits('<script src="//cdn.example.com/x.js" integrity="sha384-abc" crossorigin></script>')
        self.assertIn(("third-party-script", "cdn.example.com"), got)
        self.assertNotIn("no-sri", [k for k, _ in got])

    def test_local_and_relative_scripts_ignored(self):
        self.assertEqual(hits('<script src="/js/app.js"></script>'), [])
        self.assertEqual(hits('<script src="http://localhost:8080/x.js"></script>'), [])

    def test_tracker_detected(self):
        got = hits('<script async src="https://www.googletagmanager.com/gtag/js?id=G-1"></script>')
        self.assertIn(("tracker", "Google Analytics/Tag Manager"), got)
        self.assertIn(("tracker", "Meta Pixel/SDK"), hits("fbq('track', 'Purchase');", "a.js"))

    def test_dynamic_script(self):
        self.assertIn(("third-party-script", "dynamic script load"), hits("const s = document.createElement('script');", "a.js"))

    def test_cookie_storage_fingerprint(self):
        self.assertEqual(hits("document.cookie = 'a=b';", "a.js"), [("cookie-write", "document.cookie =")])
        self.assertIn("cookie-write", [k for k, _ in hits("ResponseCookie.from(\"s\", v)", "A.java")])
        self.assertEqual(hits("localStorage.setItem('k', v)", "a.js"), [("client-storage", "localStorage.setItem")])
        self.assertEqual(hits("c.toDataURL()", "a.js"), [("fingerprinting", "toDataURL")])

    def test_good_signals(self):
        self.assertIn("gpc-signal", [k for k, _ in hits("if (navigator.globalPrivacyControl) {}", "a.js")])
        self.assertIn("consent-check", [k for k, _ in hits("window.__tcfapi('getTCData', 2, cb)", "a.js")])

    def test_plain_code_no_hits(self):
        self.assertEqual(hits("const total = items.reduce((a, b) => a + b, 0);", "a.js"), [])


class FileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.tmp.name
        os.makedirs(os.path.join(r, "node_modules"))
        files = {
            "index.html": '<script src="https://cdn.x.com/a.js"></script>\n',
            "lib.min.js": "fbq('init')\n",
            "notes.md": "fbq('init')\n",
            os.path.join("node_modules", "m.js"): "fbq('init')\n",
        }
        for name, body in files.items():
            with open(os.path.join(r, name), "w") as f:
                f.write(body)
        with open(os.path.join(r, "bin.js"), "wb") as f:
            f.write(b"\0fbq('init')")
        self.root = r

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *args, stdin=None):
        out, err = io.StringIO(), io.StringIO()
        old = sys.stdin
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            with redirect_stdout(out), redirect_stderr(err):
                rc = t.main(list(args))
        finally:
            sys.stdin = old
        return rc, out.getvalue(), err.getvalue()

    def test_walk_scans_only_source_files(self):
        rc, out, err = self.run_main(self.root)
        self.assertEqual(rc, 0)
        self.assertEqual(len(out.strip().splitlines()), 2, out)  # third-party-script + no-sri
        self.assertIn("index.html", out)
        self.assertIn("# 2 lead(s)", err)

    def test_json_from_stdin(self):
        rc, out, _ = self.run_main("--json", "--files-from", "-", stdin=os.path.join(self.root, "index.html") + "\n")
        kinds = [json.loads(l)["kind"] for l in out.strip().splitlines()]
        self.assertEqual(kinds, ["third-party-script", "no-sri"])

    def test_missing_path(self):
        self.assertEqual(self.run_main(os.path.join(self.root, "nope.js"))[:2], (0, ""))


if __name__ == "__main__":
    unittest.main()
