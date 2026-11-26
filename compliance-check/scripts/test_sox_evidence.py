"""Tests for sox_evidence.py: the pure checks, the gh wrapper and a full run against a fake gh."""
import datetime as dt
import io
import json
import pathlib
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import sox_evidence as sx

REPO = "acme/ledger"
SINCE, UNTIL = "2026-01-01", "2026-03-31"
TODAY = dt.date(2026, 4, 10)


def ids(pack):
    return sorted((e["id"], e["severity"], e["item"]) for e in pack.exceptions)


class FakeGh(sx.Gh):
    """Answers gh calls from a dict keyed by a substring of the path; unknown paths raise GhError."""

    def __init__(self, api=None, cli=None):
        super().__init__(runner=None)
        self.api_map, self.cli_map, self.calls = api or {}, cli or {}, []

    def api(self, path, paginate=False):
        self.calls.append(path)
        for key, value in self.api_map.items():
            if key in path:
                if isinstance(value, Exception):
                    raise value
                return value
        raise sx.GhError("HTTP 404: Not Found")

    def cli(self, args):
        self.calls.append(" ".join(args))
        for key, value in self.cli_map.items():
            if key in args:
                if isinstance(value, Exception):
                    raise value
                return value
        raise sx.GhError("unknown command")


def pr(number, author="dev", reviews=(), merged_at="2026-02-01T10:00:00Z", labels=(), head="h1", merge="m1"):
    return {"number": number, "author": {"login": author}, "reviews": list(reviews),
            "mergedBy": {"login": author}, "mergedAt": merged_at, "mergeCommit": {"oid": merge},
            "labels": [{"name": n} for n in labels], "headRefOid": head}


def review(login, at="2026-02-01T09:00:00Z", state="APPROVED", commit="h1", bot=False):
    return {"author": {"login": login, "is_bot": bot}, "state": state, "submittedAt": at,
            "commit": {"oid": commit} if commit else None}


class BranchControlsTest(unittest.TestCase):
    STRONG = {
        "required_pull_request_reviews": {"required_approving_review_count": 1, "dismiss_stale_reviews": True},
        "required_status_checks": {"contexts": ["build"]},
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False}, "allow_deletions": {"enabled": False},
    }

    def test_strong_classic_protection_has_no_exceptions(self):
        pack = sx.Pack()
        sx.check_branch_controls(pack, "main", sx.branch_controls(self.STRONG, []))
        self.assertEqual(pack.exceptions, [])

    def test_no_protection_flags_every_control(self):
        pack = sx.Pack()
        sx.check_branch_controls(pack, "main", sx.branch_controls(None, None))
        self.assertEqual([e["id"] for e in pack.exceptions], ["SOX-CM1/CM2", "SOX-CM3", "SOX-CM1", "SOX-AC7"])

    def test_rulesets_supply_the_controls(self):
        rules = [
            {"type": "pull_request", "parameters": {"required_approving_review_count": 2,
                                                    "require_last_push_approval": True,
                                                    "require_code_owner_review": True}},
            {"type": "required_status_checks"}, {"type": "non_fast_forward"}, {"type": "deletion"},
        ]
        c = sx.branch_controls(None, rules)
        self.assertEqual((c["approvals"], c["last_push_approval"], c["code_owners"]), (2, True, True))
        pack = sx.Pack()
        sx.check_branch_controls(pack, "main", c)
        self.assertEqual([e["id"] for e in pack.exceptions], ["SOX-AC7"])  # admins: not enforced classically

    def test_approval_without_stale_dismissal_is_medium(self):
        weak = dict(self.STRONG, required_pull_request_reviews={"required_approving_review_count": 1})
        pack = sx.Pack()
        sx.check_branch_controls(pack, "main", sx.branch_controls(weak, []))
        self.assertEqual(ids(pack), [("SOX-CM2", "Medium", "branch main")])

    def test_status_checks_by_checks_list(self):
        p = dict(self.STRONG, required_status_checks={"checks": [{"context": "ci"}]})
        self.assertTrue(sx.branch_controls(p, [])["status_checks"])


class AccessTest(unittest.TestCase):
    def test_listing_by_highest_role(self):
        collabs = [
            {"login": "boss", "permissions": {"admin": True, "maintain": True, "push": True}},
            {"login": "lead", "permissions": {"maintain": True, "push": True}},
            {"login": "dev", "permissions": {"push": True}},
            {"login": "reader", "permissions": {"pull": True}},
        ]
        self.assertEqual(sx.access_listing(collabs), {"admin": ["boss"], "maintain": ["lead"], "write": ["dev"]})
        self.assertEqual(sx.access_listing(None), {"admin": [], "maintain": [], "write": []})


class ChangeTest(unittest.TestCase):
    def run_check(self, prs, emergency=frozenset({"hotfix"})):
        pack = sx.Pack()
        rows = sx.check_change(pack, prs, set(emergency))
        return pack, rows

    def test_independent_approval_on_final_commit_passes(self):
        pack, rows = self.run_check([pr(1, reviews=[review("rev")])])
        self.assertEqual(pack.exceptions, [])
        self.assertEqual(rows[0]["approvers"], ["rev"])

    def test_self_approval_bot_and_comments_do_not_count(self):
        reviews = [review("dev"), review("ci-bot", bot=True), review("dependabot[bot]"),
                   review("rev", state="COMMENTED")]
        pack, _ = self.run_check([pr(2, reviews=reviews)])
        self.assertEqual(ids(pack), [("SOX-CM8", "High", "PR #2")])

    def test_approval_on_an_older_commit_is_medium(self):
        pack, _ = self.run_check([pr(3, reviews=[review("rev", commit="h0")])])
        self.assertEqual(ids(pack), [("SOX-CM8", "Medium", "PR #3")])

    def test_review_without_commit_oid_counts_as_final(self):
        pack, _ = self.run_check([pr(4, reviews=[review("rev", commit=None)])])
        self.assertEqual(pack.exceptions, [])

    def test_approval_after_merge_is_not_approval_for_normal_change(self):
        pack, rows = self.run_check([pr(5, reviews=[review("rev", at="2026-02-02T00:00:00Z")])])
        self.assertEqual(ids(pack), [("SOX-CM8", "High", "PR #5")])
        self.assertEqual(rows[0]["retro_approvers"], ["rev"])

    def test_emergency_change_needs_retrospective_review(self):
        pack, rows = self.run_check([pr(6, labels=["Hotfix"])])
        self.assertEqual(ids(pack), [("SOX-CM7", "High", "PR #6")])
        self.assertTrue(rows[0]["emergency"])
        pack, _ = self.run_check([pr(7, labels=["hotfix"], reviews=[review("rev", at="2026-02-03T00:00:00Z")])])
        self.assertEqual(pack.exceptions, [])


class EnvironmentTest(unittest.TestCase):
    def test_protected_environment_passes(self):
        env = {"name": "production", "deployment_branch_policy": {"protected_branches": True},
               "protection_rules": [{"type": "required_reviewers", "prevent_self_review": True,
                                     "reviewers": [{"reviewer": {"login": "ops"}}, {"reviewer": {"slug": "sre"}}]}]}
        pack = sx.Pack()
        row = sx.check_environment(pack, env)
        self.assertEqual(pack.exceptions, [])
        self.assertEqual(row["reviewers"], ["ops", "sre"])

    def test_unprotected_and_self_review_environments(self):
        pack = sx.Pack()
        sx.check_environment(pack, {"name": "prod"})
        self.assertEqual(ids(pack), [("SOX-CM4", "Medium", "environment prod"),
                                     ("SOX-CM4/SOD1", "Medium", "environment prod")])
        pack = sx.Pack()
        sx.check_environment(pack, {"name": "prod", "deployment_branch_policy": {"x": 1},
                                    "protection_rules": [{"type": "required_reviewers",
                                                          "reviewers": [{"reviewer": {"login": "a"}}]}]})
        self.assertEqual(ids(pack), [("SOX-SOD1", "Medium", "environment prod")])


class OperationsTest(unittest.TestCase):
    def test_scheduled_workflow_whose_last_run_failed(self):
        runs = [
            {"name": "nightly", "event": "schedule", "conclusion": "success", "created_at": "2026-01-01"},
            {"name": "nightly", "event": "schedule", "conclusion": "failure", "created_at": "2026-01-02"},
            {"name": "recover", "event": "schedule", "conclusion": "failure", "created_at": "2026-01-01"},
            {"name": "recover", "event": "schedule", "conclusion": "success", "created_at": "2026-01-02"},
            {"name": "ci", "event": "pull_request", "conclusion": "failure", "created_at": "2026-01-03"},
        ]
        pack = sx.Pack()
        rows = sx.check_runs(pack, runs)
        self.assertEqual(ids(pack), [("SOX-OPS1", "Medium", "workflow nightly")])
        self.assertEqual({r["workflow"]: r["failures"] for r in rows}, {"ci": 1, "nightly": 1, "recover": 1})

    def test_retention_gap(self):
        since = dt.date(2026, 1, 1)
        self.assertEqual(sx.retention_gap(90, since, dt.date(2026, 3, 1)), 0)
        self.assertEqual(sx.retention_gap(90, since, dt.date(2026, 4, 10)), 9)
        self.assertEqual(sx.retention_gap(None, since, dt.date(2027, 1, 1)), 0)


class GhWrapperTest(unittest.TestCase):
    def runner(self, code=0, out="", err="", exc=None):
        def run(cmd, **kw):
            self.cmd, self.kw = cmd, kw
            if exc:
                raise exc
            return subprocess.CompletedProcess(cmd, code, out, err)
        return run

    def test_api_get_with_timeout(self):
        gh = sx.Gh(self.runner(out='{"a": 1}'))
        self.assertEqual(gh.api("repos/x/y"), {"a": 1})
        self.assertEqual(self.cmd, ["gh", "api", "-X", "GET", "repos/x/y"])
        self.assertEqual(self.kw["timeout"], sx.GH_TIMEOUT_S)

    def test_paginate_flattens_lists_and_wrapped_pages(self):
        gh = sx.Gh(self.runner(out=json.dumps([[1, 2], [3], {"total_count": 2, "workflow_runs": [4, 5]}, "x"])))
        self.assertEqual(gh.api("p", paginate=True), [1, 2, 3, 4, 5])
        self.assertIn("--slurp", self.cmd)
        self.assertEqual(sx.Gh(self.runner(out="")).api("p", paginate=True), [])

    def test_errors(self):
        with self.assertRaisesRegex(sx.GhError, "HTTP 403"):
            sx.Gh(self.runner(code=1, err="warn\ngh: Forbidden (HTTP 403)\n")).api("p")
        with self.assertRaisesRegex(sx.GhError, "gh failed"):
            sx.Gh(self.runner(code=1)).cli(["x"])
        with self.assertRaisesRegex(sx.GhError, "timed out"):
            sx.Gh(self.runner(exc=subprocess.TimeoutExpired("gh", 1))).api("p")
        with self.assertRaisesRegex(sx.GhError, "not JSON"):
            sx.Gh(self.runner(out="<html>")).api("p")


def full_fake(**overrides):
    api = {
        f"repos/{REPO}/collaborators": [{"login": "boss", "permissions": {"admin": True}},
                                        {"login": "dev", "permissions": {"push": True}}],
        f"repos/{REPO}/keys": [{"id": 9, "title": "deployer", "read_only": False}, {"id": 8, "read_only": True}],
        f"repos/{REPO}/teams": [],
        f"repos/{REPO}/branches/main/protection": BranchControlsTest.STRONG,
        f"repos/{REPO}/rules/branches/main": [{"type": "pull_request", "ruleset_id": 77, "parameters": {}}],
        f"repos/{REPO}/rulesets/77": {"name": "main rules",
                                      "bypass_actors": [{"actor_type": "RepositoryRole", "actor_id": 5,
                                                         "bypass_mode": "always"}]},
        f"repos/{REPO}/commits?sha=main": [
            {"sha": "m1" * 20, "parents": [{}], "commit": {"verification": {"verified": True}}},
            {"sha": "d1" * 20, "parents": [{}], "commit": {"verification": {"verified": False}}},
            {"sha": "r1" * 20, "parents": [{}], "commit": {}},
            {"sha": "x1" * 20, "parents": [{}, {}], "commit": {}},
        ],
        f"commits/{'d1' * 20}/pulls": [],
        f"commits/{'r1' * 20}/pulls": [{"number": 12, "merged_at": "2026-02-01"}],
        f"commits/{'e1' * 20}/pulls": sx.GhError("HTTP 500"),
        f"repos/{REPO}/environments": [{"name": "production", "deployment_branch_policy": {"p": 1},
                                        "protection_rules": [{"type": "required_reviewers", "prevent_self_review": True,
                                                              "reviewers": [{"reviewer": {"login": "ops"}}]}]},
                                       {"name": "staging"}],
        f"repos/{REPO}/deployments?environment=production": [
            {"id": 1, "sha": "m1" * 20, "created_at": "2026-02-01T00:00:00Z"},
            {"id": 2, "sha": "d1" * 20, "created_at": "2026-02-02T00:00:00Z"},
            {"id": 3, "sha": "e1" * 20, "created_at": "2026-02-03T00:00:00Z"},
            {"id": 4, "sha": "zz" * 20, "created_at": "2025-12-01T00:00:00Z"},
        ],
        f"repos/{REPO}/releases": [],
        f"repos/{REPO}/actions/runs": [
            {"name": "billing-close", "event": "schedule", "conclusion": "failure", "created_at": "2026-03-01"}],
        "artifact-and-log-retention": {"days": 90},
    }
    cli = {
        "pr": [pr(11, reviews=[review("rev")], merge="m1" * 20), pr(13, merge=None)],
        "issue": [{"number": 40, "state": "CLOSED", "closedByPullRequestsReferences": []},
                  {"number": 41, "state": "CLOSED", "closedByPullRequestsReferences": [{"number": 11}]}],
        "repo": {"nameWithOwner": REPO},
    }
    api.update(overrides.pop("api", {}))
    cli.update(overrides.pop("cli", {}))
    return FakeGh(api, cli)


class GatherAllTest(unittest.TestCase):
    def gather(self, gh, environment="production", max_lookups=200):
        return sx.gather_all(gh, REPO, SINCE, UNTIL, environment, {"hotfix"}, ["incident"], max_lookups, TODAY)

    def test_full_run_flags_each_area(self):
        gh = full_fake(api={f"repos/{REPO}": {"default_branch": "main"}})
        pack = self.gather(gh)
        got = ids(pack)
        for expected in [
            ("SOX-AC7", "Medium", "deploy key deployer"),
            ("SOX-AC7", "Medium", "ruleset main rules"),
            ("SOX-CM8", "High", "PR #13"),
            ("SOX-CM8", "High", f"commit {'d1' * 6}"),
            ("SOX-CM9", "High", "deployment 2 to production"),
            ("SOX-EVD3", "Info", "branch main"),
            ("SOX-OPS1", "Medium", "workflow billing-close"),
            ("SOX-OPS3", "Low", "incident #40"),
            ("SOX-EVD2", "Medium", "workflow logs"),
        ]:
            self.assertIn(expected, got)
        self.assertNotIn(("SOX-CM8", "High", f"commit {'r1' * 6}"), got)  # rebase-merged via PR 12
        self.assertFalse(any("deployment 4" in e["item"] for e in pack.exceptions))  # outside the period
        self.assertFalse(any("staging" in e["item"] for e in pack.exceptions))  # filtered by --environment
        self.assertTrue(any("e1e1e1e1e1e1: PR lookup failed" in g for g in pack.gaps))
        self.assertEqual(pack.evidence["access"]["listing"]["admin"], ["boss"])
        self.assertEqual(pack.evidence["change"]["unsigned_commits"], 3)

    def test_missing_permissions_become_gaps_not_crashes(self):
        gh = FakeGh(api={}, cli={})
        pack = self.gather(gh, environment=None)
        self.assertTrue(any(g.startswith("access/collaborators: not gathered (HTTP 404") for g in pack.gaps))
        self.assertTrue(any("no matching GitHub environment" in g for g in pack.gaps))
        # Unknown default branch falls back to main; no protection gives the CM exceptions.
        self.assertIn(("SOX-CM3", "High", "branch main"), ids(pack))

    def test_lookup_cap_and_pr_cap_are_reported(self):
        gh = full_fake(api={f"repos/{REPO}": {"default_branch": "main"}},
                       cli={"pr": [pr(n, reviews=[review("rev")], merge=f"q{n}") for n in range(1000)]})
        pack = self.gather(gh, max_lookups=0)
        self.assertTrue(any("1000 PRs listed" in g for g in pack.gaps))
        self.assertTrue(any("stopped PR lookups at 0" in g for g in pack.gaps))
        self.assertFalse(any(e["item"].startswith("commit ") for e in pack.exceptions))


class OutputAndMainTest(unittest.TestCase):
    def test_summary_and_manifest(self):
        pack = sx.Pack()
        pack.flag("SOX-OPS3", "Low", "incident #1", "x")
        pack.flag("SOX-CM8", "High", "PR #2", "y")
        pack.evidence = {"access": {"listing": {"admin": ["a"], "write": []}}}
        text = sx.render_summary(pack, REPO, SINCE, UNTIL, "now")
        self.assertLess(text.index("PR #2"), text.index("incident #1"))
        self.assertIn("| write | – |", text)
        self.assertIn("High 1 · Medium 0 · Low 1 · Info 0", text)
        empty = sx.render_summary(sx.Pack(), REPO, SINCE, UNTIL, "now")
        self.assertIn("| – | – | none | – |", empty)
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "pack"
            sx.write_pack(pack, out, text)
            manifest = (out / "MANIFEST.sha256").read_text().splitlines()
            self.assertEqual([m.split()[1] for m in manifest], ["access.json", "exceptions.json", "summary.md"])
            import hashlib
            digest = hashlib.sha256((out / "summary.md").read_bytes()).hexdigest()
            self.assertIn(f"{digest}  summary.md", manifest)

    def test_main_writes_pack(self):
        gh = full_fake(api={f"repos/{REPO}": {"default_branch": "main"}})
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as out:
            code = sx.main(["--since", SINCE, "--until", UNTIL, "--out", tmp, "--environment", "production"],
                           gh=gh, today=TODAY)
            self.assertEqual(code, 0)
            self.assertIn("SOX-CM9", (pathlib.Path(tmp) / "summary.md").read_text())
        self.assertIn("exceptions High:", out.getvalue())

    def test_main_default_until_and_repo_lookup_failure(self):
        gh = FakeGh(cli={"repo": sx.GhError("not a repo")})
        with redirect_stderr(io.StringIO()) as err:
            self.assertEqual(sx.main(["--since", SINCE], gh=gh), 2)
        self.assertIn("cannot find the repository", err.getvalue())

    def test_bad_arguments(self):
        for argv in (["--since", "2026/01/01"], ["--since", "2026-02-30"], ["--since", "2026-05-01", "--until", "2026-04-01"],
                     ["--since", SINCE, "--repo", "bad repo"], ["--since", SINCE, "--environment", "x;y"],
                     ["--since", SINCE, "--incident-label", "a$b"], ["--since", SINCE, "--max-lookups", "-1"], []):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()):
                self.assertEqual(sx.main(argv, gh=FakeGh()), 2)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(sx.main(["--help"]), 0)


if __name__ == "__main__":
    unittest.main()
