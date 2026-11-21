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
