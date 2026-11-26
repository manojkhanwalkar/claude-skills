"""Unit tests for ui_scan.py. Run: python3 -I -m unittest discover -s <this dir> -p 'test_*.py'"""
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui_scan as u  # noqa: E402


def kinds(text, path="a.html"):
    return [h.kind for h in u.scan_text(path, text)]


def png(w, h):
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", w, h) + b"\x00" * 8


def jpeg(w, h):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
    sof = b"\xff\xc0" + struct.pack(">H", 17) + b"\x08" + struct.pack(">HH", h, w) + b"\x00" * 10
    return b"\xff\xd8" + b"\xff" + app0 + sof


class MarkupTest(unittest.TestCase):
    def test_clean_markup_has_no_leads(self):
        html = ('<img src="a.avif" width="800" height="600" loading="lazy" alt="">'
                '<img src="h.avif" :width="w" [height]="h" loading="eager" fetchpriority="high" alt="">'
                '<iframe src="/v" loading="lazy"></iframe><script src="/a.js" defer></script>'
                '<script src="/b.js" async></script><script type="module" src="/c.js"></script><script>x()</script>')
        self.assertEqual(kinds(html), [])

    def test_each_markup_defect(self):
        self.assertEqual(kinds('<img src="a.png" loading="lazy">'), ["img-no-size"])
        self.assertEqual(kinds('<img src="a.png" width="1" height="1">'), ["img-loading-unset"])
        self.assertEqual(kinds('<img src="a" width=1 height=1 loading="lazy" fetchpriority="high">'), ["lazy-and-high"])
        self.assertEqual(kinds('<iframe src="/v"></iframe>'), ["iframe-eager"])
        self.assertEqual(kinds('<script src="/a.js"></script>'), ["script-blocking"])

    def test_line_numbers_and_jsx(self):
        hits = u.scan_text("C.tsx", "const a = 1;\n\n<img src={x} width={1} height={2} />")
        self.assertEqual([(h.line, h.kind) for h in hits], [(3, "img-loading-unset")])

    def test_markup_not_scanned_in_plain_scripts(self):
        self.assertEqual(kinds('const s = "<img src=a>";', "a.js"), [])


class StyleAndScriptTest(unittest.TestCase):
    def test_css(self):
        css = '@import "x.css";\n@font-face { font-family: A; src: url(a.woff2); }\n' \
              '@font-face { font-family: B; font-display: swap; }'
        self.assertEqual(kinds(css, "s.css"), ["css-import", "font-display"])

    def test_inline_style_in_html_only_checks_fonts(self):
        html = '<style>@import "x.css"; @font-face { font-family: A; }</style>'
        self.assertEqual(kinds(html, "i.html"), ["font-display"])

    def test_whole_library_imports(self):
        js = ("import _ from 'lodash';\nimport * as fns from \"date-fns\";\nimport { map } from 'lodash-es';\n"
              "import debounce from 'lodash/debounce';\nconst m = require('moment');")
        hits = u.scan_text("a.ts", js)
        self.assertEqual([(h.line, h.kind) for h in hits], [(1, "whole-library"), (2, "whole-library"), (5, "whole-library")])
        self.assertIn("moment", hits[2].detail)


class ImageTest(unittest.TestCase):
    def test_sizes_from_headers(self):
        self.assertEqual(u.image_size(png(3000, 200)), (3000, 200))
        self.assertEqual(u.image_size(b"GIF89a" + struct.pack("<HH", 640, 480)), (640, 480))
        self.assertEqual(u.image_size(jpeg(4032, 3024)), (4032, 3024))
        vp8x = b"RIFF\x00\x00\x00\x00WEBPVP8X" + b"\x00" * 8 + (2999).to_bytes(3, "little") + (99).to_bytes(3, "little")
        self.assertEqual(u.image_size(vp8x), (3000, 100))
        bits = (1023) | (511 << 14)
        vp8l = b"RIFF\x00\x00\x00\x00WEBPVP8L" + b"\x00" * 5 + bits.to_bytes(4, "little") + b"\x00" * 5
        self.assertEqual(u.image_size(vp8l), (1024, 512))
        vp8 = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 10 + struct.pack("<HH", 800, 600)
        self.assertEqual(u.image_size(vp8), (800, 600))
        avif = b"\x00\x00\x00\x1cftypavif" + b"\x00" * 20 + b"\x00\x00\x00\x14ispe\x00\x00\x00\x00" + struct.pack(">II", 5000, 4000)
        self.assertEqual(u.image_size(avif), (5000, 4000))

    def test_unknown_or_truncated(self):
        self.assertIsNone(u.image_size(b"not an image"))
        self.assertIsNone(u.image_size(b"\xff\xd8\xff\xe0\x00"))
        self.assertIsNone(u.image_size(b"RIFF\x00\x00\x00\x00WEBPXXXX" + b"\x00" * 20))
        # JPEG with padding bytes and a restart marker before the frame header.
        self.assertEqual(u.image_size(b"\xff\xd8\x00\xff\xff\xd0" + jpeg(10, 20)[2:]), (10, 20))

    def test_scan_image_limits(self):
        hits = u.scan_image("big.gif", 300 * 1024, b"GIF89a" + struct.pack("<HH", 3000, 10), 200, 50, 2560)
        self.assertEqual([h.kind for h in hits], ["image-heavy", "gif-animation", "image-dimensions"])
        self.assertEqual([h.kind for h in u.scan_image("i.svg", 60 * 1024, b"<svg", 200, 50, 2560)], ["image-heavy"])
        self.assertEqual(u.scan_image("ok.png", 10 * 1024, png(800, 600), 200, 50, 2560), [])


class PathsAndCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, self.cwd)
        os.makedirs("src/__tests__")
        os.makedirs("node_modules/x")
        with open("src/index.html", "w") as f:
            f.write('<script src="/a.js"></script>')
        with open("src/__tests__/a.html", "w") as f:
            f.write('<script src="/a.js"></script>')
        with open("node_modules/x/b.html", "w") as f:
            f.write('<script src="/a.js"></script>')
        with open("src/hero.png", "wb") as f:
            f.write(png(4000, 3000) + b"\x00" * (250 * 1024))
        with open("src/notes.txt", "w") as f:
            f.write("<script src=x>")
        os.symlink("src/index.html", "link.html")
        os.mkfifo("pipe.html") if hasattr(os, "mkfifo") else None

    def test_scan_paths_skips_tests_vendor_and_specials(self):
        hits = u.scan_paths(["."])
        got = sorted((h.path, h.kind) for h in hits)
        self.assertIn((os.path.join("src", "index.html"), "script-blocking"), got)
        self.assertIn((os.path.join("src", "hero.png"), "image-heavy"), got)
        self.assertIn((os.path.join("src", "hero.png"), "image-dimensions"), got)
        self.assertFalse(any("__tests__" in p or "node_modules" in p or "pipe" in p for p, _ in got))

    def test_single_file_and_missing_file(self):
        self.assertEqual([h.kind for h in u.scan_paths(["src/index.html"])], ["script-blocking"])
        self.assertEqual(u.scan_paths(["does-not-exist.html"]), [])

    def run_main(self, argv, stdin=None):
        out = io.StringIO()
        old = sys.stdin
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            with redirect_stdout(out):
                code = u.main(argv)
        finally:
            sys.stdin = old
        return code, out.getvalue()

    def test_cli_text_json_and_files_from(self):
        code, out = self.run_main(["src"])
        self.assertEqual(code, 0)
        self.assertIn("script-blocking", out)
        self.assertIn("ui_scan: image-dimensions 1, image-heavy 1, script-blocking 1", out)
        code, out = self.run_main(["--json", "src/index.html"])
        self.assertEqual(json.loads(out)[0]["kind"], "script-blocking")
        code, out = self.run_main(["--files-from", "-"], stdin="src/index.html\n\ngone.html\n")
        self.assertIn("script-blocking", out)
        code, out = self.run_main(["--files-from", "-"], stdin="gone.html\n")
        self.assertIn("no existing files", out)
        with open("list.txt", "w") as f:
            f.write("src/notes.txt\n")
        code, out = self.run_main(["--files-from", "list.txt"])
        self.assertIn("no leads", out)


if __name__ == "__main__":
    unittest.main()
