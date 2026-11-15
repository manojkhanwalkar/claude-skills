"""Unit tests for scan_a11y.py. Run: python3 -I -m unittest discover -s <this dir> -p 'test_*.py'"""
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan_a11y as a  # noqa: E402

PAGE = '<!doctype html><html lang="en"><head><title>T</title></head><body>{}</body></html>'


def kinds(body, path="a.html", page=True):
    text = PAGE.format(body) if page else body
    return [h.kind for h in a.scan_text(path, text)]


class MarkupTest(unittest.TestCase):
    def test_clean_page_has_no_leads(self):
        body = ('<h1>T</h1><h2>S</h2><img src="x.png" alt="Logo"><img src="d.png" alt="">'
                '<label for="e">Email</label><input id="e" type="email">'
                '<label>Name <input name="n"></label><input aria-label="Search" type="search">'
                '<input type="hidden" name="csrf"><button>Save</button>'
                '<button aria-label="Close"><svg aria-hidden="true"></svg></button>'
                '<a href="/help">Help</a><a href="/home"><img src="h.png" alt="Home"></a>'
                '<div role="button" tabindex="0" onclick="go()">Go</div>')
        self.assertEqual(kinds(body), [])

    def test_each_defect(self):
        cases = {
            '<img src="x.png">': "img-alt",
            '<input id="q" type="text">': "input-label",
            '<select name="s"></select>': "input-label",
            '<button><svg></svg></button>': "button-name",
            '<a href="/x"><i class="icon"></i></a>': "link-name",
            '<input type="text" aria-label="q" tabindex="3">': "positive-tabindex",
            '<div onclick="go()">Go</div>': "click-no-key",
            '<span @click="go">Go</span>': "click-no-key",
            '<a href="#" onclick="go()">Go</a>': "anchor-no-href",
            '<a onClick={go}>Go</a>': "anchor-no-href",
            '<button aria-hidden="true">X</button>': "aria-hidden-focus",
            '<video src="v.mp4" autoplay></video>': "autoplay",
            '<h1>A</h1><h3>B</h3>': "heading-skip",
            '<input type="password" aria-label="p" onpaste="return false">': "paste-blocked",
        }
        for body, kind in cases.items():
            self.assertIn(kind, kinds(body), body)

    def test_page_level_defects(self):
        self.assertEqual(kinds("<html><head><title>x</title></head></html>", page=False), ["html-lang"])
        self.assertEqual(kinds('<html lang="en"><head><title> </title></head></html>', page=False), ["page-title"])
        self.assertIn("no-zoom", kinds('<meta name="viewport" content="width=device-width, user-scalable=no">'))
        self.assertIn("no-zoom", kinds('<meta name="viewport" content="width=device-width, maximum-scale=1">'))
        self.assertNotIn("no-zoom", kinds('<meta name="viewport" content="width=device-width, initial-scale=1">'))

    def test_jsx_names_and_labels(self):
        jsx = ('export const F = () => (<form><label htmlFor="z">ZIP</label><input id="z" />'
               '<button onClick={() => save({a: 1 > 0})}>Save</button><img src={logo} alt="" /></form>);')
        self.assertEqual(kinds(jsx, "F.jsx", page=False), [])
        self.assertEqual(kinds('const x = () => <img src={logo} />;', "F.tsx", page=False), ["img-alt"])

    def test_fragments_and_templates_are_not_pages(self):
        self.assertEqual(kinds('<div><img src="a" alt="a"></div>', "part.vue", page=False), [])

    def test_unknown_inner_text_is_not_guessed(self):
        self.assertEqual(kinds("<button>" + "x" * 5000, page=False), [])


class ReviewRegressionTest(unittest.TestCase):
    """Cases from the independent review of the first version."""

    def test_angular_bindings(self):
        self.assertIn("click-no-key", kinds('<div (click)="go()">Go</div>', "a.component.html", page=False))
        self.assertIn("anchor-no-href", kinds('<a (click)="go()">Go</a>', "a.component.html", page=False))
        self.assertEqual(kinds('<button [attr.aria-label]="label"><i></i></button>', "a.component.html", page=False), [])
        self.assertEqual(kinds('<label [for]="id">X</label><input [id]="id">', "a.component.html", page=False), [])

    def test_components_are_not_html_elements(self):
        jsx = 'const F = () => (<><Button label="Save" onClick={s} /><Input label="Email" /><Select label="C" /></>);'
        self.assertEqual(kinds(jsx, "F.jsx", page=False), [])
        self.assertIn("img-alt", kinds('<IMG SRC="x.png">'))  # plain HTML is case-insensitive

    def test_unquoted_and_bound_label_targets(self):
        self.assertEqual(kinds("<label for=e>E</label><input id=e>"), [])
        self.assertEqual(kinds('<label :for="id">E</label><input :id="id">', "a.vue", page=False), [])

    def test_comments_are_ignored_and_lines_kept(self):
        hits = a.scan_text("a.html", PAGE.format('<!-- <img src="x"> -->\n<!--\n-->\n<img src="y">'))
        self.assertEqual([(h.kind, h.line) for h in hits], [("img-alt", 4)])
        self.assertEqual(kinds("<!-- unclosed <img src=x>", page=False), [])

    def test_bad_viewport_value_does_not_crash(self):
        self.assertEqual(kinds('<meta name="viewport" content="maximum-scale=1..0">'), ["no-zoom"])  # read as 1, like browsers

    def test_border_none_is_not_a_focus_style_and_0px_counts_as_removed(self):
        self.assertEqual(kinds("button:focus { outline: none; border: none; }", "a.css", page=False), ["outline-none"])
        self.assertEqual(kinds("a:focus { outline: 0px }", "a.css", page=False), ["outline-none"])
        self.assertEqual(kinds("a { outline: 0 } a:focus-visible { border-bottom: 2px solid #000; }", "a.css", page=False), [])

    def test_hostile_braces_and_many_labels_stay_linear(self):
        for text, path in (("<a{>" * 20_000, "a.jsx"), ("if (i<n){ x => { y } }\n" * 20_000, "a.js"),
                           ("<label>A</label><input>\n" * 20_000, "a.html"), ("<style>" * 20_000, "a.html")):
            start = time.monotonic()
            a.scan_text(path, text)
            self.assertLess(time.monotonic() - start, 10, path)


class StyleTest(unittest.TestCase):
    def test_outline_removed_without_replacement(self):
        self.assertEqual(kinds("button:focus { outline: none; }", "a.css", page=False), ["outline-none"])

    def test_outline_removed_with_focus_visible_style(self):
        css = "button { outline: 0 } button:focus-visible { outline: 2px solid #005fcc; }"
        self.assertEqual(kinds(css, "a.css", page=False), [])

    def test_style_block_in_html_reports_its_line(self):
        hits = a.scan_text("a.html", PAGE.format("") + "\n<style>\n a { outline: none }\n</style>")
        self.assertEqual([(h.kind, h.line) for h in hits], [("outline-none", 3)])


class PerformanceTest(unittest.TestCase):
    def test_large_and_hostile_input_stays_fast(self):
        start = time.monotonic()
        a.scan_text("a.html", "<div " * 100_000)
        a.scan_text("a.html", '<img alt="x">\n' * 50_000)
        a.scan_text("a.jsx", "<a onClick={" + "{" * 50_000)
        self.assertLess(time.monotonic() - start, 15)


class FileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.tmp.name
        os.makedirs(os.path.join(r, "node_modules"))
        files = {"index.html": PAGE.format('<img src="x">'), "x.min.js": "<img src=x>", "README.md": "<img src=x>",
                 os.path.join("node_modules", "m.html"): "<img src=x>", "app.js": "const n = 1 < 2;"}
        for name, body in files.items():
            with open(os.path.join(r, name), "w") as f:
                f.write(body)
        with open(os.path.join(r, "bin.html"), "wb") as f:
            f.write(b"\0<img src=x>")
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
                rc = a.main(list(args))
        finally:
            sys.stdin = old
        return rc, out.getvalue(), err.getvalue()

    def test_walk_scans_ui_files_only(self):
        rc, out, err = self.run_main(self.root)
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip().splitlines(), [os.path.join(self.root, "index.html") + ":1: img-alt: <img> without alt (use alt=\"\" if decorative)"])
        self.assertIn("# 1 lead(s)", err)

    def test_json_files_from_and_default_dir(self):
        rc, out, _ = self.run_main("--json", "--files-from", "-", stdin=os.path.join(self.root, "index.html") + "\n")
        self.assertEqual(json.loads(out)["kind"], "img-alt")
        listing = os.path.join(self.root, "list.txt")
        with open(listing, "w") as f:
            f.write(os.path.join(self.root, "index.html") + "\n")
        self.assertIn("img-alt", self.run_main("--files-from", listing)[1])
        old = os.getcwd()
        os.chdir(self.root)
        try:
            self.assertIn("img-alt", self.run_main()[1])
        finally:
            os.chdir(old)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs FIFOs")
    def test_fifo_and_oversized_files_skipped(self):
        os.mkfifo(os.path.join(self.root, "pipe.html"))
        big = os.path.join(self.root, "big.html")
        with open(big, "w") as f:
            f.write("<img src=x>" + "x" * a.MAX_FILE_BYTES)
        self.assertEqual(self.run_main(self.root)[1].count("img-alt"), 1)

    def test_missing_path(self):
        self.assertEqual(self.run_main(os.path.join(self.root, "nope.html"))[:2], (0, ""))


if __name__ == "__main__":
    unittest.main()
