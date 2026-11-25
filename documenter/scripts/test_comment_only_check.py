"""Unit tests for comment_only_check.py. Run: python3 -I -m unittest discover -s <this dir> -p 'test_*.py'"""
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comment_only_check as c  # noqa: E402

JAVA = "class A {\n  int f(int i) {\n    return i\n      * 2;\n  }\n}\n"
PY = 'import os  # noqa: F401\n\n\ndef f(x):\n    return x + 1  # add one\n'


class RepoTest(unittest.TestCase):
    """Each test gets a fresh repository with one commit; START is that commit."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.git("config", "commit.gpgsign", "false")

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", self.repo, *args], check=True, capture_output=True)

    def write(self, path, text):
        full = os.path.join(self.repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def start(self, files):
        for path, text in files.items():
            self.write(path, text)
        self.git("add", "-A")
        self.git("commit", "-qm", "start")
        return subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"], check=True,
                              capture_output=True, text=True).stdout.strip()

    def failures(self, files, edits):
        start = self.start(files)
        for path, text in edits.items():
            self.write(path, text)
        return c.check(self.repo, start)[1]


class CLikeTest(RepoTest):
    def test_added_and_changed_comments_pass(self):
        new = ("/** Adds things. */\nclass A {\n  /**\n   * Doubles.\n   *\n   * @param i x\n   */\n"
               "  int f(int i) { // inline\n    return i\n      * 2; /* why */\n  }\n}\n")
        self.assertEqual(self.failures({"A.java": JAVA}, {"A.java": new}), [])

    def test_continuation_line_starting_with_star_is_code(self):
        new = JAVA.replace("* 2;", "* 3;")
        self.assertEqual(len(self.failures({"A.java": JAVA}, {"A.java": new})), 1)

    def test_increment_at_column_zero_is_code(self):
        fails = self.failures({"s.js": "let c = 0;\n++c;\n"}, {"s.js": "let c = 0;\n++c; c = 9;\n"})
        self.assertIn("line 2: code changed", fails[0])

    def test_removed_code_line(self):
        fails = self.failures({"s.ts": "a();\nb();\n"}, {"s.ts": "a();\n"})
        self.assertIn("code removed: b();", fails[0])

    def test_code_after_comment_close_is_code(self):
        fails = self.failures({"A.kt": "/* x */ val a = 1\n"}, {"A.kt": "/* y */ val a = 2\n"})
        self.assertEqual(len(fails), 1)

    def test_comment_marker_inside_string_is_code(self):
        old = 'const u = "http://a.example";\nconst t = `//x`;\n'
        new = 'const u = "http://b.example";\nconst t = `//x`;\n'
        self.assertEqual(len(self.failures({"u.js": old}, {"u.js": new})), 1)

    def test_text_block_and_char_literal(self):
        old = 'class T {\n  String s = """\n    // not a comment\n    """;\n  char q = \'"\';\n}\n'
        new = old.replace("// not a comment", "// changed")
        self.assertEqual(len(self.failures({"T.java": old}, {"T.java": new})), 1)

    def test_rust_lifetimes_and_doc_comments(self):
        old = "fn f<'a>(x: &'a str) -> &'a str { x }\n"
        new = "/// Returns `x` unchanged.\n///\n/// # Panics\n/// Never.\n" + old
        self.assertEqual(self.failures({"l.rs": old}, {"l.rs": new}), [])

    def test_go_directive_change_fails(self):
        old = "//go:build linux\n\npackage p\n"
        fails = self.failures({"p.go": old}, {"p.go": old.replace("linux", "darwin")})
        self.assertEqual(fails, ["p.go: a tool directive comment changed"])

    def test_go_doc_comment_passes(self):
        old = "package p\n\nfunc F() int { return 1 }\n"
        new = "package p\n\n// F returns one.\nfunc F() int { return 1 }\n"
        self.assertEqual(self.failures({"p.go": old}, {"p.go": new}), [])

    def test_ts_directive_change_fails(self):
        old = "// @ts-ignore\nconst a: number = 'x';\n"
        fails = self.failures({"a.ts": old}, {"a.ts": "const a: number = 'x';\n"})
        self.assertIn("directive", fails[0])

    def test_cgo_file_needs_a_look(self):
        old = 'package p\n\n// #include <stdio.h>\nimport "C"\n'
        fails = self.failures({"c.go": old}, {"c.go": old.replace("stdio", "stdlib")})
        self.assertIn("cgo", fails[0])

    def test_crlf_files_compare_by_content(self):
        old = "class A {\r\n}\r\n"
        self.assertEqual(self.failures({"A.cs": old}, {"A.cs": "/// <summary>A.</summary>\r\n" + old}), [])


class PythonTest(RepoTest):
    def test_docstrings_and_comments_pass(self):
        new = ('"""Module."""\nimport os  # noqa: F401\n\n\ndef f(x):\n    """Add one."""\n'
               "    return x + 1  # plus one\n\n\nclass K:\n    \"\"\"K.\"\"\"\n")
        old = PY + "\n\nclass K:\n    pass\n"
        new = new.replace('    """K."""\n', '    """K."""\n    pass\n')
        self.assertEqual(self.failures({"m.py": old}, {"m.py": new}), [])

    def test_code_change_fails(self):
        fails = self.failures({"m.py": PY}, {"m.py": PY.replace("x + 1", "x + 2")})
        self.assertEqual(fails, ["m.py: code changed (syntax tree differs)"])

    def test_directive_change_fails(self):
        fails = self.failures({"m.py": PY}, {"m.py": PY.replace("  # noqa: F401", "")})
        self.assertEqual(fails, ["m.py: a tool directive comment changed"])

    def test_unparseable_file(self):
        fails = self.failures({"m.py": PY}, {"m.py": PY + "def (:\n"})
        self.assertIn("does not parse", fails[0])


class FilesTest(RepoTest):
    def test_new_package_doc_files_pass(self):
        edits = {"p/doc.go": "// Package p does things.\npackage p\n",
                 "a/package-info.java": "/** Alerts. */\npackage com.x.a;\n",
                 "notes.txt": "untracked, not source: ignored\n"}
        self.assertEqual(self.failures({"A.java": JAVA}, edits), [])

    def test_new_package_doc_with_code_fails(self):
        fails = self.failures({"A.java": JAVA}, {"p/doc.go": "package p\n\nvar X = 1\n"})
        self.assertIn("more than comments", fails[0])

    def test_new_source_file_fails_untracked_or_staged(self):
        fails = self.failures({"A.java": JAVA}, {"B.java": "class B {}\n"})
        self.assertIn("new file", fails[0])
        self.git("add", "B.java")
        self.assertIn("new file", c.check(self.repo, "HEAD")[1][0])

    def test_rename_and_delete_fail(self):
        start = self.start({"A.java": JAVA, "B.java": "class B {}\n"})
        self.git("mv", "A.java", "C.java")
        self.git("rm", "-q", "B.java")
        fails = c.check(self.repo, start)[1]
        self.assertTrue(any("renamed from A.java" in f for f in fails))
        self.assertTrue(any("B.java: deleted" in f for f in fails))

    def test_unsupported_file_fails(self):
        fails = self.failures({"README.md": "x\n"}, {"README.md": "y\n"})
        self.assertEqual(fails, ["README.md: not a supported source file"])

    def test_type_change_fails(self):
        start = self.start({"A.java": JAVA})
        os.remove(os.path.join(self.repo, "A.java"))
        os.symlink("elsewhere", os.path.join(self.repo, "A.java"))
        self.assertIn("unexpected", c.check(self.repo, start)[1][0])

    def test_committed_edits_are_checked_too(self):
        start = self.start({"A.java": JAVA})
        self.write("A.java", JAVA.replace("2;", "3;"))
        self.git("commit", "-qam", "docs")
        self.assertEqual(len(c.check(self.repo, start)[1]), 1)


class MainTest(RepoTest):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = c.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_pass_and_fail_exit_codes(self):
        start = self.start({"A.java": JAVA})
        self.write("A.java", "/** A. */\n" + JAVA)
        code, out, _ = self.run_main(start, "--repo", self.repo)
        self.assertEqual((code, out.strip()), (0, "COMMENT-ONLY CHECK: PASS (1 files)"))
        self.write("A.java", JAVA.replace("i\n", "i + 1\n"))
        code, out, _ = self.run_main(start, "--repo", self.repo)
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("FAIL A.java: line 3"))
        self.assertIn("COMMENT-ONLY CHECK: FAIL (1 problems in 1 files)", out)

    def test_bad_start_and_not_a_repo(self):
        self.start({"A.java": JAVA})
        self.assertEqual(self.run_main("nope", "--repo", self.repo)[0], 2)
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(self.run_main("HEAD", "--repo", empty)[0], 2)


if __name__ == "__main__":
    unittest.main()
