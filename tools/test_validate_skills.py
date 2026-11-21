"""Tests for validate_skills.py: each rule fails on a broken skill and passes on a good one."""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import validate_skills as v

GOOD = "---\nname: {name}\ndescription: Does one thing. Use when asked. Not for other things.\n---\n\n# Body\n"


class SkillRepo:
    """A throwaway repository with skills and a README."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def skill(self, name, text=None, directory=None):
        d = self.root / (directory or name)
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(text if text is not None else GOOD.format(name=name), encoding="utf-8")
        return d

    def readme(self, *names):
        rows = "".join(f"| [`{n}`]({n}/SKILL.md) | ... |\n" for n in names)
        (self.root / "README.md").write_text("# Skills\n\n| Skill | What |\n|---|---|\n" + rows, encoding="utf-8")

    def close(self):
        self._tmp.cleanup()


class ValidateSkillsTest(unittest.TestCase):

    def setUp(self):
        self.repo = SkillRepo()

    def tearDown(self):
        self.repo.close()

    def problems(self):
        return v.validate(self.repo.root)

    def test_a_good_repository_has_no_problems(self):
        self.repo.skill("good-skill")
        self.repo.readme("good-skill")
        self.assertEqual([], self.problems())

    def test_names_must_be_lowercase_hyphenated_and_match_the_directory(self):
        self.repo.skill("bad_name", GOOD.format(name="bad_name"))
        self.repo.skill("upper", GOOD.format(name="Upper"))
        self.repo.skill("other-dir", GOOD.format(name="some-name"))
        self.repo.skill("long", GOOD.format(name="a" * 65))
        self.repo.readme("bad_name", "upper", "other-dir", "long")
        text = "\n".join(self.problems())
        self.assertIn("bad_name/SKILL.md: name 'bad_name' must be", text)
        self.assertIn("upper/SKILL.md: name 'Upper' must be", text)
        self.assertIn("differs from its directory 'other-dir'", text)
        self.assertIn("long/SKILL.md: name", text)

    def test_descriptions_are_required_bounded_and_free_of_angle_brackets(self):
        self.repo.skill("missing", "---\nname: missing\n---\n")
        self.repo.skill("blank", "---\nname: blank\ndescription: '  '\n---\n")
        self.repo.skill("too-long", "---\nname: too-long\ndescription: " + "x" * 1025 + "\n---\n")
        self.repo.skill("tags", "---\nname: tags\ndescription: Reads <file> and writes it.\n---\n")
        self.repo.readme("missing", "blank", "too-long", "tags")
        text = "\n".join(self.problems())
        self.assertIn("missing/SKILL.md: description is missing", text)
        self.assertIn("blank/SKILL.md: description is missing", text)
        self.assertIn("too-long/SKILL.md: description is 1025 characters", text)
        self.assertIn("tags/SKILL.md: description contains < or >", text)

    def test_exactly_1024_characters_is_allowed(self):
        self.repo.skill("edge", "---\nname: edge\ndescription: " + "x" * 1024 + "\n---\n")
        self.repo.readme("edge")
        self.assertEqual([], self.problems())

    def test_frontmatter_must_exist_be_strict_yaml_and_a_mapping(self):
        self.repo.skill("none", "# No frontmatter\n")
        self.repo.skill("unclosed", "---\nname: unclosed\n")
        self.repo.skill("colon", "---\nname: colon\ndescription: Args: a value: with colons\n---\n")
        self.repo.skill("listy", "---\n- a\n- b\n---\n")
        self.repo.readme("none", "unclosed", "colon", "listy")
        text = "\n".join(self.problems())
        self.assertIn("none/SKILL.md: no frontmatter", text)
        self.assertIn("unclosed/SKILL.md: no frontmatter", text)
        self.assertIn("colon/SKILL.md: frontmatter is not valid YAML", text)
        self.assertIn("listy/SKILL.md: frontmatter is not a mapping", text)

    def test_every_skill_needs_a_readme_row(self):
        self.repo.skill("listed")
        self.repo.skill("forgotten")
        self.repo.readme("listed")
        self.assertEqual(["README.md: no row for skill forgotten (a link to forgotten/SKILL.md)"], self.problems())

    def test_a_missing_readme_is_a_problem(self):
        self.repo.skill("alone")
        self.assertEqual(["README.md is missing"], self.problems())

    def test_relative_links_must_resolve_but_urls_anchors_and_code_examples_are_ignored(self):
        d = self.repo.skill("linked", GOOD.format(name="linked") + (
            "See [ref](references/ok.md), [section](references/ok.md#part), [web](https://example.com),\n"
            "[top](#body), [mail](mailto:a@example.com) and [gone](references/missing.md).\n"
            "~~~markdown\n[example](not/a/real/file.md)\n```\n[still example](nope.md)\n```\n~~~\n"))
        (d / "references").mkdir()
        (d / "references" / "ok.md").write_text("[up](../SKILL.md) [bad](../nothing.md)\n", encoding="utf-8")
        self.repo.readme("linked")
        self.assertEqual(sorted([
            "linked/SKILL.md: link to references/missing.md points at nothing",
            "linked/references/ok.md: link to ../nothing.md points at nothing",
        ]), sorted(self.problems()))

    def test_readme_links_are_checked_too(self):
        self.repo.skill("real")
        self.repo.readme("real", "ghost")
        self.assertEqual(["README.md: link to ghost/SKILL.md points at nothing"], self.problems())

    def test_directories_without_a_skill_are_ignored(self):
        self.repo.skill("real")
        (self.repo.root / "templates").mkdir()
        (self.repo.root / "templates" / "x.yml").write_text("a: 1\n", encoding="utf-8")
        self.repo.readme("real")
        self.assertEqual([], self.problems())

    def test_name_pattern_rejects_leading_trailing_and_double_hyphens_and_a_trailing_newline(self):
        for i, bad in enumerate(["-lead", "trail-", "dou--ble"]):
            self.repo.skill(f"dir{i}", GOOD.format(name=bad))
        self.repo.skill("nl", "---\nname: \"nl\\n\"\ndescription: x\n---\n")
        self.repo.readme("dir0", "dir1", "dir2", "nl")
        text = "\n".join(self.problems())
        for bad in ["'-lead'", "'trail-'", "'dou--ble'", "'nl\\n'"]:
            self.assertIn(f"name {bad} must be", text)

    def test_names_of_exactly_64_characters_are_allowed(self):
        name = "a" * 64
        self.repo.skill(name)
        self.repo.readme(name)
        self.assertEqual([], self.problems())

    def test_reserved_words_are_refused_in_names(self):
        self.repo.skill("claude-helper")
        self.repo.skill("my-anthropic-tool")
        self.repo.readme("claude-helper", "my-anthropic-tool")
        text = "\n".join(self.problems())
        self.assertIn("name 'claude-helper' contains a reserved word", text)
        self.assertIn("name 'my-anthropic-tool' contains a reserved word", text)

    def test_only_keys_accepted_on_upload_are_allowed(self):
        self.repo.skill("extra", "---\nname: extra\ndescription: x\nversion: 2\n---\n")
        self.repo.skill("ok-keys", "---\nname: ok-keys\ndescription: x\nlicense: MIT\nallowed-tools: Read\n"
                                   "metadata: {a: b}\ncompatibility: any\n---\n")
        self.repo.readme("extra", "ok-keys")
        self.assertEqual(["extra/SKILL.md: frontmatter keys ['version'] are not accepted on upload "
                          "(allowed: ['allowed-tools', 'compatibility', 'description', 'license', 'metadata', 'name'])"],
                         self.problems())

    def test_unsafe_yaml_tags_are_refused(self):
        self.repo.skill("tagged", "---\nname: tagged\ndescription: !!python/object/apply:os.getcwd []\n---\n")
        self.repo.readme("tagged")
        self.assertIn("tagged/SKILL.md: frontmatter is not valid YAML", "\n".join(self.problems()))

    def test_a_byte_order_mark_and_crlf_line_endings_are_fine(self):
        self.repo.skill("bom", "\ufeff---\r\nname: bom\r\ndescription: x\r\n---\r\n")
        self.repo.readme("bom")
        self.assertEqual([], self.problems())

    def test_an_indented_dashes_line_inside_a_block_scalar_does_not_end_the_frontmatter(self):
        body = "---\nname: block\ndescription: |\n  first\n  ---\n  " + "y" * 1030 + "\n---\n"
        self.repo.skill("block", body)
        self.repo.readme("block")
        self.assertIn("block/SKILL.md: description is", "\n".join(self.problems()))

    def test_link_forms_and_code_are_handled(self):
        d = self.repo.skill("forms", GOOD.format(name="forms") + (
            "[t1](ok.md 'single') [t2](ok.md (paren)) [t3](<ok.md>) [t4](file(1).md) [t5](ok%20two.md)\n"
            "[t6](ok.md?raw=1) [t7](HTTPS://x) [t8](//cdn.example.com/a) [t9](ftp://x) [t10](~/x.md)\n"
            "`[code](nope.md)` and ```[inline](nope.md)``` stay examples; [t11](<repo url>) is a placeholder\n"
            "- item\n    - [nested](gone4.md)\n"
            "[ref]: missing-ref.md\n"
            "[bad1](gone.md 'title') [bad2](<gone2.md>) [bad3](/etc/hostname) [bad4](../../outside.md)\n"
            "```text\n[fenced](nope.md)\n~~~\n[still fenced](nope.md)\n```\n[after](gone3.md)\n"))
        for f in ["ok.md", "file(1).md", "ok two.md"]:
            (d / f).write_text("x\n", encoding="utf-8")
        self.repo.readme("forms")
        self.assertEqual(sorted([
            "forms/SKILL.md: link to missing-ref.md points at nothing",
            "forms/SKILL.md: link to gone.md points at nothing",
            "forms/SKILL.md: link to gone2.md points at nothing",
            "forms/SKILL.md: link to /etc/hostname leaves the repository",
            "forms/SKILL.md: link to ../../outside.md leaves the repository",
            "forms/SKILL.md: link to gone3.md points at nothing",
            "forms/SKILL.md: link to gone4.md points at nothing",
        ]), sorted(self.problems()))

    def test_fence_rules(self):
        self.repo.skill("fences", GOOD.format(name="fences") + (
            "````text\n```\n[inside long fence](nope1.md)\n````\n"      # a shorter fence doesn't close a longer one
            "```text\n```python\n[inside, info-string line](nope2.md)\n```\n"   # a fence with an info string doesn't close
            "```one-line code```\n[after one-line](gone1.md)\n"          # not a fence: links after it are checked
            "[paren](gone(1).md)\n"))
        self.repo.readme("fences")
        self.assertEqual(sorted([
            "fences/SKILL.md: link to gone1.md points at nothing",
            "fences/SKILL.md: link to gone(1).md points at nothing",
        ]), sorted(self.problems()))

    def test_an_indented_opening_line_is_not_frontmatter(self):
        self.repo.skill("indented", " ---\nname: indented\ndescription: x\n---\n")
        self.repo.readme("indented")
        self.assertEqual(["indented/SKILL.md: no frontmatter (a `---` line, YAML, then a `---` line)"], self.problems())

    def test_main_prints_problems_and_exits_non_zero(self):
        self.repo.skill("bad_one", GOOD.format(name="bad_one"))
        self.repo.readme("bad_one")
        out = io.StringIO()
        with redirect_stdout(out):
            code = v.main(["validate_skills.py", str(self.repo.root)])
        self.assertEqual(1, code)
        self.assertIn("1 skills checked, 1 problem(s)", out.getvalue())

    def test_main_exits_zero_when_all_is_well(self):
        self.repo.skill("fine")
        self.repo.readme("fine")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, v.main(["validate_skills.py", str(self.repo.root)]))
        self.assertIn("1 skills checked, 0 problem(s)", out.getvalue())


if __name__ == "__main__":
    unittest.main()
