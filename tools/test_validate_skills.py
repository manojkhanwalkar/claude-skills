"""Tests for validate_skills.py: each rule fails on a broken skill and passes on a good one."""

import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import validate_skills as v

GOOD = "---\nname: {name}\ndescription: Does one thing. Use when asked. Not for other things. Args - none.\n---\n\n# Body\n"


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

    def readme(self, *names, log=None):
        rows = "".join(f"| [`{n}`]({n}/SKILL.md) | ... |\n" for n in names)
        changes = "".join(f"| 2026-11-25 | #1 | Add {n} |\n" for n in (names if log is None else log))
        (self.root / "README.md").write_text("# Skills\n\n| Skill | What |\n|---|---|\n" + rows
                                             + "\n## Change log\n\n| Date | PR | Change |\n|---|---|---|\n"
                                             + changes, encoding="utf-8")

    def marketplace(self, *entries, source="./", raw=None):
        d = self.root / ".claude-plugin"
        d.mkdir(exist_ok=True)
        text = raw if raw is not None else json.dumps(
            {"name": "m", "owner": {"name": "o"},
             "plugins": [{"name": "p", "source": source, "strict": False, "skills": list(entries)}]})
        (d / "marketplace.json").write_text(text, encoding="utf-8")

    def manifest(self, *entries, raw=None, **fields):
        d = self.root / ".claude-plugin"
        d.mkdir(exist_ok=True)
        text = raw if raw is not None else json.dumps(
            {"name": "p", "version": "1.0.0", "skills": list(entries), **fields})
        (d / "plugin.json").write_text(text, encoding="utf-8")

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
        self.repo.skill("edge", "---\nname: edge\ndescription: Args - none " + "x" * 1012 + "\n---\n")
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
        self.repo.readme("listed", log=["listed", "forgotten"])
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
        self.repo.skill("extra", "---\nname: extra\ndescription: Args - x\nversion: 2\n---\n")
        self.repo.skill("ok-keys", "---\nname: ok-keys\ndescription: Args - x\nlicense: MIT\nallowed-tools: Read\n"
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
        self.repo.skill("bom", "\ufeff---\r\nname: bom\r\ndescription: Args - x\r\n---\r\n")
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
            "[t6](ok.md?raw=1) [t6b](?raw=1) [t7](HTTPS://x) [t8](//cdn.example.com/a) [t9](ftp://x) [t10](~/x.md)\n"
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

    def test_descriptions_need_an_args_part(self):
        self.repo.skill("no-args", "---\nname: no-args\ndescription: Does a thing. Arguments vary.\n---\n")
        self.repo.skill("args-none", "---\nname: args-none\ndescription: Does a thing. Args - none.\n---\n")
        self.repo.readme("no-args", "args-none")
        self.assertEqual(['no-args/SKILL.md: description has no Args part (end it with "Args - [PR] [--flag]" '
                          'or "Args - none")'], self.problems())

    def test_every_skill_needs_a_change_log_row_naming_it_as_a_whole_word(self):
        self.repo.skill("doc")
        self.repo.skill("doc-tool")
        self.repo.skill("logged")
        # "doc-tool" and "docs" don't name "doc"; the skill table above the log doesn't count.
        self.repo.readme("doc", "doc-tool", "logged", log=["doc-tool and docs", "`logged`"])
        self.assertEqual(["README.md: no change-log row names skill doc"], self.problems())

    def test_a_readme_without_a_change_log_section_is_a_problem(self):
        self.repo.skill("solo")
        (self.repo.root / "README.md").write_text("| [`solo`](solo/SKILL.md) |\n", encoding="utf-8")
        self.assertEqual(['README.md: no "## Change log" section'], self.problems())

    def test_the_change_log_ends_at_the_next_section(self):
        self.repo.skill("late")
        (self.repo.root / "README.md").write_text(
            "| [`late`](late/SKILL.md) |\n\n## Change log\n\n| Date | PR | Change |\n\n## Later\n\n| x | late |\n",
            encoding="utf-8")
        self.assertEqual(["README.md: no change-log row names skill late"], self.problems())

    def test_quoted_reference_and_script_paths_must_exist_here_or_in_a_sibling(self):
        d = self.repo.skill("paths", GOOD.format(name="paths") + (
            "Read `references/own.md`, then `scripts/run.py`; perf's `references/shared.md` too.\n"
            "Missing: `references/gone.md` and `scripts/gone.py`; `references/<x>.md` is a placeholder.\n"
            "Run ${CLAUDE_SKILL_DIR}/scripts/run.py, \"${CLAUDE_SKILL_DIR}/../perf/references/shared.md\",\n"
            "${CLAUDE_SKILL_DIR}/../templates/x.yml and ${CLAUDE_SKILL_DIR}/../other/scripts/nope.py;\n"
            "a clone path breaks plugin installs even when it exists: ~/.claude/skills/paths/scripts/run.py.\n"))
        (d / "references").mkdir()
        (d / "references" / "own.md").write_text("x\n", encoding="utf-8")
        (d / "scripts").mkdir()
        (d / "scripts" / "run.py").write_text("x = 1\n", encoding="utf-8")
        sibling = self.repo.skill("perf")
        (sibling / "references").mkdir()
        (sibling / "references" / "shared.md").write_text("x\n", encoding="utf-8")
        self.repo.readme("paths", "perf")
        self.assertEqual(sorted([
            "paths/SKILL.md: references/gone.md exists in no skill",
            "paths/SKILL.md: scripts/gone.py exists in no skill",
            "paths/SKILL.md: ${CLAUDE_SKILL_DIR}/../templates/x.yml points at nothing in this repository",
            "paths/SKILL.md: ${CLAUDE_SKILL_DIR}/../other/scripts/nope.py points at nothing in this repository",
            "paths/SKILL.md: ~/.claude/skills/paths/scripts/run.py only exists in a clone; a plugin install "
            "puts the skills elsewhere (write ${CLAUDE_SKILL_DIR}/...)",
        ]), sorted(self.problems()))

    def test_quoted_paths_may_not_climb_out_of_the_skill_or_repository(self):
        outside = Path(self.repo.root).parent / f"{Path(self.repo.root).name}-outside.md"
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        outside.write_text("x\n", encoding="utf-8")
        d = self.repo.skill("climb", GOOD.format(name="climb") + (
            f"Read `references/../../../{outside.name}` and ${{CLAUDE_SKILL_DIR}}/../../{outside.name}.\n"))
        (d / "references").mkdir()
        self.repo.readme("climb")
        self.assertEqual(sorted([
            f"climb/SKILL.md: references/../../../{outside.name} exists in no skill",
            f"climb/SKILL.md: ${{CLAUDE_SKILL_DIR}}/../../{outside.name} points at nothing in this repository",
        ]), sorted(self.problems()))

    SECRET = {(hashlib.sha256(b"secretproj").hexdigest(), len("secretproj"))}
    SUFFIX = " (this repo is public: use a generic example)"

    def write(self, *rels, text="# from secretproj\n"):
        for rel in rels:
            f = self.repo.root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")

    def test_private_project_names_are_refused_in_every_file_outside_git_but_hidden_folders(self):
        self.repo.skill("leaky", GOOD.format(name="leaky") + "Ported SecretProj to SecretProjPy.\n")
        self.repo.readme("leaky")
        self.write("templates/a.yml", ".github/workflows/c.yml", "notes.md", "security/audit.md")
        self.write(".venv/d.md", "leaky/e.png", "leaky/__pycache__/f.txt")
        with patch.object(v, "PRIVATE_NAMES", self.SECRET):
            problems = self.problems()
        self.assertEqual(sorted([
            ".github/workflows/c.yml: private project name in secretproj" + self.SUFFIX,
            "leaky/SKILL.md: private project name in SecretProj, SecretProjPy" + self.SUFFIX,
            "notes.md: private project name in secretproj" + self.SUFFIX,
            "security/audit.md: private project name in secretproj" + self.SUFFIX,
            "templates/a.yml: private project name in secretproj" + self.SUFFIX,
        ]), sorted(problems))

    def test_in_a_git_checkout_only_tracked_files_are_scanned(self):
        self.repo.skill("clean")
        self.repo.readme("clean")
        self.write("tracked.md", "synced/untracked.md")
        subprocess.run(["git", "init", "-q", str(self.repo.root)], check=True)
        subprocess.run(["git", "-C", str(self.repo.root), "add", "tracked.md", "clean", "README.md"], check=True)
        with patch.object(v, "PRIVATE_NAMES", self.SECRET):
            self.assertEqual(["tracked.md: private project name in secretproj" + self.SUFFIX], self.problems())

    def test_hyphens_underscores_and_dots_inside_a_name_are_ignored_but_spaces_are_not(self):
        with patch.object(v, "PRIVATE_NAMES", self.SECRET):
            self.assertEqual(["Secret_Proj", "secret-proj", "secret.projPy"],
                             v.private_names("secret-proj, Secret_Proj and secret.projPy; secret proj is prose"))

    def test_the_built_in_denylist_is_well_formed(self):
        self.assertTrue(v.PRIVATE_NAMES)
        for digest, length in v.PRIVATE_NAMES:
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            self.assertGreater(length, 3)

    def test_descriptions_over_the_listing_budget_warn_but_do_not_fail(self):
        self.repo.skill("wordy", "---\nname: wordy\ndescription: Args - none " + "x" * 290 + "\n---\n")
        self.repo.skill("at-budget", "---\nname: at-budget\ndescription: Args - none " + "x" * 288 + "\n---\n")
        self.repo.skill("broken", "---\nname: broken\ndescription: Args: a: b\n---\n")
        self.repo.skill("bare", "# no frontmatter\n")
        self.repo.readme("wordy", "at-budget", "broken", "bare")
        self.assertEqual(["wordy/SKILL.md: description is 302 characters, over the 300-character listing budget "
                          "(keep the whole skill listing small)"], v.warnings(self.repo.root))
        self.repo.skill("broken", "---\nname: broken\n---\n")
        self.assertEqual(1, len(v.warnings(self.repo.root)))

    def test_main_prints_warnings_as_github_annotations_in_actions(self):
        self.repo.skill("wordy", "---\nname: wordy\ndescription: Args - none " + "x" * 390 + "\n---\n")
        self.repo.readme("wordy")
        for env, prefix in [("true", "::warning::wordy"), ("", "warning: wordy")]:
            out = io.StringIO()
            with patch.dict(os.environ, {"GITHUB_ACTIONS": env}), redirect_stdout(out):
                self.assertEqual(0, v.main(["validate_skills.py", str(self.repo.root)]))
            self.assertIn(prefix, out.getvalue())
            self.assertIn("1 skills checked, 0 problem(s), 1 warning(s)", out.getvalue())

    def test_main_prints_problems_and_exits_non_zero(self):
        self.repo.skill("bad_one", GOOD.format(name="bad_one"))
        self.repo.readme("bad_one")
        out = io.StringIO()
        with redirect_stdout(out):
            code = v.main(["validate_skills.py", str(self.repo.root)])
        self.assertEqual(1, code)
        self.assertIn("1 skills checked, 1 problem(s), 0 warning(s)", out.getvalue())

    def test_main_exits_zero_when_all_is_well(self):
        self.repo.skill("fine")
        self.repo.readme("fine")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, v.main(["validate_skills.py", str(self.repo.root)]))
        self.assertIn("1 skills checked, 0 problem(s), 0 warning(s)", out.getvalue())

    def test_marketplace_must_list_every_skill_exactly(self):
        for name in ("alpha", "beta"):
            self.repo.skill(name)
        self.repo.readme("alpha", "beta")
        self.repo.marketplace("./alpha", "./beta")
        self.assertEqual([], self.problems())
        self.repo.marketplace("./alpha", "./alpha", "./gone", "./gone", "beta", {"x": 1}, {"x": 1})
        m = ".claude-plugin/marketplace.json"
        self.assertEqual([f"{m}: './alpha' is listed more than once",
                          f"{m}: './gone' is listed more than once",
                          f"{m}: skill beta is not in a plugin's skills list (add \"./beta\")",
                          f"{m}: './gone' in a skills list is not a skill directory (write ./<dir>)",
                          f"{m}: 'beta' in a skills list is not a skill directory (write ./<dir>)",
                          f"{m}: {{'x': 1}} in a skills list is not a skill directory (write ./<dir>)"],
                         self.problems())

    def test_marketplace_without_a_root_skills_list_or_with_bad_json_fails(self):
        self.repo.skill("solo")
        self.repo.readme("solo")
        m = ".claude-plugin/marketplace.json"
        self.repo.marketplace("./solo", source="./plugins/x")
        self.assertEqual([f'{m}: no plugin with "source": "./" has a skills list'], self.problems())
        for raw in ("[1, 2]", '{"plugins": 5}'):
            self.repo.marketplace(raw=raw)
            self.assertEqual([f'{m}: no plugin with "source": "./" has a skills list'], self.problems())
        self.repo.marketplace(raw="{not json")
        [problem] = self.problems()
        self.assertTrue(problem.startswith(f"{m}: not valid JSON"), problem)

    def test_plugin_json_lists_every_skill_and_the_marketplace_defers_to_it(self):
        for name in ("alpha", "beta"):
            self.repo.skill(name)
        self.repo.readme("alpha", "beta")
        p, m = ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"
        self.repo.manifest("./alpha", "./beta")
        self.assertEqual([], self.problems())
        self.repo.manifest("./alpha", "./alpha", "./gone", version="1.0")
        self.assertEqual([f"{p}: version '1.0' is not MAJOR.MINOR.PATCH",
                          f"{p}: './alpha' is listed more than once",
                          f"{p}: skill beta is not in a plugin's skills list (add \"./beta\")",
                          f"{p}: './gone' in a skills list is not a skill directory (write ./<dir>)"],
                         self.problems())
        self.repo.manifest("./alpha", "./beta")
        self.repo.marketplace("./alpha", "./beta")  # name "p", strict false, a skills list
        self.assertEqual([f"{m}: entry 'p' lists skills; with a plugin.json, list them there only",
                          f"{m}: entry 'p' sets strict: false; with a plugin.json, leave strict at its default"],
                         self.problems())
        self.repo.marketplace(raw=json.dumps({"plugins": [{"name": "q", "source": "./"},
                                                          {"name": "x", "source": "./x", "skills": []}]}))
        self.assertEqual([f"{m}: no entry with \"source\": \"./\" is named 'p', so the plugin can't be installed "
                          "from the marketplace", f"{m}: entry 'q' is not named like plugin.json ('p')"], self.problems())
        self.repo.marketplace(raw=json.dumps({"plugins": [{"name": "p", "source": "./x"}]}))
        self.assertEqual([f"{m}: no entry with \"source\": \"./\" is named 'p', so the plugin can't be installed "
                          "from the marketplace"], self.problems())
        self.repo.marketplace(raw=json.dumps({"plugins": [{"name": "p", "source": "./"}]}))
        self.assertEqual([], self.problems())

    def test_plugin_json_that_is_broken_or_has_no_skills_list_fails(self):
        self.repo.skill("solo")
        self.repo.readme("solo")
        p, m = ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"
        self.repo.manifest(raw='{"name": "p", "version": 3}')
        self.assertEqual([f"{p}: version 3 is not MAJOR.MINOR.PATCH", f"{p}: no skills list"], self.problems())
        self.repo.manifest(raw="[1]")
        self.assertEqual([f"{p}: not a JSON object"], self.problems())
        self.repo.manifest(raw="{oops")
        [problem] = self.problems()
        self.assertTrue(problem.startswith(f"{p}: not valid JSON"), problem)
        self.repo.manifest("./solo")
        self.repo.marketplace(raw="{oops")
        [problem] = self.problems()
        self.assertTrue(problem.startswith(f"{m}: not valid JSON"), problem)

    def test_this_repository_marketplace_matches_its_skills(self):
        root = Path(__file__).resolve().parent.parent
        dirs = [d.name for d in v.skill_dirs(root)]
        self.assertEqual([], v.check_marketplace(root, dirs))


if __name__ == "__main__":
    unittest.main()
