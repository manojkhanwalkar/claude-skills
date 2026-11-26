"""Tests for sox_evidence.py: the pure checks, the gh wrapper and a full run against a fake gh."""
import datetime as dt
import hashlib
import io
import json
import pathlib
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import sox_evidence as sx

REPO = "acme/ledger"
SINCE, UNTIL = "2026-01-01", "2026-03-31"
TODAY = dt.date(2026, 4, 10)


def ids(pack):
    return sorted((e["id"], e["severity"], e["item"]) for e in pack.exceptions)


class FakeGh(sx.Gh):
    """Answers gh calls from a dict keyed by a substring of the path; unknown paths raise HTTP 404."""

    def __init__(self, api=None, cli=None):
        super().__init__(runner=None)
        self.api_map, self.cli_map, self.calls = api or {}, cli or {}, []

    def api(self, path, paginate=False):
        self.calls.append(path)
        for key, value in self.api_map.items():
            # The bare repository path matches only itself; other keys match as substrings.
            if key == path or (key != f"repos/{REPO}" and key in path):
                if isinstance(value, Exception):
                    raise value
                return value
        raise sx.GhError("HTTP 404: Not Found")

    def cli(self, args):
        self.calls.append(args)
        for key, value in self.cli_map.items():
            if key in args:
                if isinstance(value, Exception):
                    raise value
                return value
        raise sx.GhError("unknown command")


def pr(number, author="dev", reviews=(), merged_at="2026-02-01T10:00:00Z", labels=(), head="h1", merge="m1"):
    # The shape `gh pr list --json` returns: people carry login and name (no type or is_bot).
    return {"number": number, "author": {"login": author, "name": "Dev Person", "id": "U1"},
            "reviews": list(reviews), "mergedBy": {"login": author, "name": "Dev Person"},
            "mergedAt": merged_at, "mergeCommit": {"oid": merge} if merge else None,
            "labels": [{"name": n} for n in labels], "headRefOid": head}


def review(login, at="2026-02-01T09:00:00Z", state="APPROVED", commit="h1"):
    return {"author": {"login": login}, "state": state, "submittedAt": at,
            "commit": {"oid": commit} if commit else None}


def commit(sha, parents=(), verified=False):
    # The commits API shape, including the author's name and email that the pack must drop.
    return {"sha": sha, "parents": [{"sha": p} for p in parents], "author": {"login": "dev"},
            "commit": {"verification": {"verified": verified},
                       "author": {"name": "Dev Person", "email": "dev@example.com"}}}


class BranchControlsTest(unittest.TestCase):
    STRONG = {
        "required_pull_request_reviews": {"required_approving_review_count": 1, "dismiss_stale_reviews": True},
        "required_status_checks": {"contexts": ["build"]},
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False}, "allow_deletions": {"enabled": False},
    }

    def check(self, protection, rules):
        pack = sx.Pack()
        sx.check_branch_controls(pack, "main", sx.branch_controls(protection, rules))
        return pack

    def test_strong_classic_protection_has_no_exceptions(self):
        self.assertEqual(self.check(self.STRONG, []).exceptions, [])

    def test_admins_bypass_flagged_only_under_classic_protection(self):
        weak = dict(self.STRONG, enforce_admins={"enabled": False})
        self.assertEqual(ids(self.check(weak, [])), [("SOX-AC7", "Medium", "branch main")])

    def test_no_protection_flags_the_change_controls(self):
        self.assertEqual([e["id"] for e in self.check(None, None).exceptions],
                         ["SOX-CM1/CM2", "SOX-CM3", "SOX-CM1"])

    def test_rulesets_alone_supply_the_controls(self):
        rules = [
            {"type": "pull_request", "parameters": {"required_approving_review_count": 2,
                                                    "require_last_push_approval": True,
                                                    "require_code_owner_review": True}},
            {"type": "required_status_checks"}, {"type": "non_fast_forward"}, {"type": "deletion"},
        ]
        c = sx.branch_controls(None, rules)
        self.assertEqual((c["approvals"], c["last_push_approval"], c["code_owners"]), (2, True, True))
        self.assertEqual(self.check(None, rules).exceptions, [])  # no AC7: rulesets bind admins

    def test_approval_without_stale_dismissal_is_medium(self):
        weak = dict(self.STRONG, required_pull_request_reviews={"required_approving_review_count": 1})
        self.assertEqual(ids(self.check(weak, [])), [("SOX-CM2", "Medium", "branch main")])

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
    def run_check(self, prs, emergency=frozenset({"hotfix"}), bots=sx.KNOWN_BOTS):
        pack = sx.Pack()
        rows = sx.check_change(pack, prs, set(emergency), bots)
        return pack, rows

    def test_independent_approval_on_final_commit_passes(self):
        pack, rows = self.run_check([pr(1, reviews=[review("rev")])])
        self.assertEqual(pack.exceptions, [])
        self.assertEqual(rows[0]["approvers"], ["rev"])

    def test_self_approval_bots_and_comments_do_not_count(self):
        reviews = [review("dev"), review("copilot-pull-request-reviewer"), review("GitHub-Actions"),
                   review("dependabot[bot]"), review("rev", state="COMMENTED")]
        pack, _ = self.run_check([pr(2, reviews=reviews)])
        self.assertEqual(ids(pack), [("SOX-CM8", "High", "PR #2")])

    def test_extra_bot_logins(self):
        pack, _ = self.run_check([pr(2, reviews=[review("approve-app")])], bots=sx.KNOWN_BOTS | {"approve-app"})
        self.assertEqual(ids(pack), [("SOX-CM8", "High", "PR #2")])
        self.assertTrue(sx.is_bot("Some-App[bot]", set()))
        self.assertFalse(sx.is_bot(None, set()))

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

    def test_minimise_pr_keeps_only_logins(self):
        slim = sx.minimise_pr(pr(8, reviews=[review("rev")]))
        self.assertEqual(slim["author"], {"login": "dev"})
        self.assertEqual(slim["mergedBy"], {"login": "dev"})
        self.assertEqual(slim["reviews"][0]["author"], {"login": "rev"})
        self.assertNotIn("Dev Person", json.dumps(slim))
        self.assertEqual(sx.minimise_pr({"number": 1})["author"], {"login": None})


class MainlineTest(unittest.TestCase):
    def test_first_parent_chain_skips_merged_branch_commits(self):
        commits = [commit("M", ["B", "F2"]), commit("F2", ["F1"]), commit("B", ["A"]), commit("F1", ["A"]),
                   commit("A", ["outside"])]
        self.assertEqual([c["sha"] for c in sx.mainline(commits)], ["M", "B", "A"])
        self.assertEqual(sx.mainline([]), [])
        self.assertEqual([c["sha"] for c in sx.mainline([commit("R")])], ["R"])

    def test_cycle_in_bad_data_terminates(self):
        self.assertEqual(len(sx.mainline([commit("X", ["Y"]), commit("Y", ["X"])])), 2)


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

    def test_paginate_flattens_lists_and_wrapped_pages_with_longer_timeout(self):
        gh = sx.Gh(self.runner(out=json.dumps([[1, 2], [3], {"total_count": 2, "workflow_runs": [4, 5]}, "x"])))
        self.assertEqual(gh.api("p", paginate=True), [1, 2, 3, 4, 5])
        self.assertIn("--slurp", self.cmd)
        self.assertEqual(self.kw["timeout"], sx.GH_PAGINATED_TIMEOUT_S)
        self.assertEqual(sx.Gh(self.runner(out="")).api("p", paginate=True), [])

    def test_errors(self):
        with self.assertRaisesRegex(sx.GhError, "HTTP 403"):
            sx.Gh(self.runner(code=1, err="warn\ngh: Forbidden (HTTP 403)\n")).api("p")
        with self.assertRaisesRegex(sx.GhError, "gh failed"):
            sx.Gh(self.runner(code=1)).cli(["x"])
        with self.assertRaisesRegex(sx.GhError, "gh failed"):
            sx.Gh(self.runner(code=1, err="\n  \n")).cli(["x"])
        with self.assertRaisesRegex(sx.GhError, "timed out"):
            sx.Gh(self.runner(exc=subprocess.TimeoutExpired("gh", 1))).api("p")
        with self.assertRaisesRegex(sx.GhError, "not installed"):
            sx.Gh(self.runner(exc=FileNotFoundError("gh"))).api("p")
        with self.assertRaisesRegex(sx.GhError, "not JSON"):
            sx.Gh(self.runner(out="<html>")).api("p")


L1, M1, D1, R1, F1, E1 = ("l1" * 20, "m1" * 20, "d1" * 20, "r1" * 20, "f1" * 20, "e1" * 20)


def full_fake(api=None, cli=None):
    base_api = {
        f"repos/{REPO}/collaborators": [{"login": "boss", "permissions": {"admin": True}},
                                        {"login": "dev", "permissions": {"push": True}}],
        f"repos/{REPO}/keys": [{"id": 9, "title": "deployer", "read_only": False}, {"id": 8, "read_only": True}],
        f"repos/{REPO}/teams": [],
        f"repos/{REPO}/branches/main/protection": BranchControlsTest.STRONG,
        f"repos/{REPO}/rules/branches/main": [{"type": "pull_request", "ruleset_id": 77, "parameters": {}}],
        f"repos/{REPO}/rulesets/77": {"name": "main rules",
                                      "bypass_actors": [{"actor_type": "RepositoryRole", "actor_id": 5,
                                                         "bypass_mode": "always"}]},
        # Mainline: L1 (a local merge, no PR) -> M1 (PR 11's squash) -> D1 (direct push) -> R1 (rebased PR 12).
        # F1 came in as L1's second parent and is never looked up.
        f"repos/{REPO}/commits?sha=main": [commit(L1, [M1, F1]), commit(F1, [R1]), commit(M1, [D1], True),
                                           commit(D1, [R1]), commit(R1, [])],
        f"commits/{L1}/pulls": [],
        f"commits/{D1}/pulls": [],
        f"commits/{R1}/pulls": [{"number": 12, "merged_at": "2026-02-01"}],
        f"commits/{E1}/pulls": sx.GhError("HTTP 500"),
        f"repos/{REPO}/environments": [{"name": "Production EU", "deployment_branch_policy": {"p": 1},
                                        "protection_rules": [{"type": "required_reviewers", "prevent_self_review": True,
                                                              "reviewers": [{"reviewer": {"login": "ops"}}]}]},
                                       {"name": "staging"}],
        f"repos/{REPO}/deployments?environment=Production%20EU": [
            {"id": 1, "sha": M1, "created_at": "2026-02-01T00:00:00Z"},
            {"id": 2, "sha": D1, "created_at": "2026-02-02T00:00:00Z"},
            {"id": 3, "sha": E1, "created_at": "2026-02-03T00:00:00Z"},
            {"id": 4, "sha": "zz" * 20, "created_at": "2025-12-01T00:00:00Z"},
        ],
        f"repos/{REPO}/releases": [],
        f"repos/{REPO}/actions/runs": [
            {"name": "billing-close", "event": "schedule", "conclusion": "failure", "created_at": "2026-03-01",
             "actor": {"login": "dev"}, "head_commit": {"author": {"name": "Dev Person", "email": "dev@example.com"}}}],
        "artifact-and-log-retention": {"days": 90},
    }
    # FakeGh matches by substring in insertion order, so overrides go first.
    merged_api = {**(api or {}), **{k: v for k, v in base_api.items() if k not in (api or {})},
                  f"repos/{REPO}": {"default_branch": "main"}}
    base_cli = {
        "pr": [pr(11, reviews=[review("rev")], merge=M1), pr(13, merge=None)],
        "issue": [{"number": 40, "state": "CLOSED", "closedByPullRequestsReferences": []},
                  {"number": 41, "state": "CLOSED", "closedByPullRequestsReferences": [{"number": 11}]}],
        "repo": {"nameWithOwner": REPO},
    }
    return FakeGh(merged_api, {**base_cli, **(cli or {})})


class GatherAllTest(unittest.TestCase):
    def gather(self, gh, environment="Production EU", max_lookups=200):
        return sx.gather_all(gh, REPO, SINCE, UNTIL, environment, {"hotfix"}, ["incident"], max_lookups, TODAY)

    def test_full_run_flags_each_area(self):
        gh = full_fake()
        pack = self.gather(gh)
        got = ids(pack)
        for expected in [
            ("SOX-AC7", "Medium", "deploy key deployer"),
            ("SOX-AC7", "Medium", "ruleset main rules"),
            ("SOX-CM8", "High", "PR #13"),
            ("SOX-CM8", "High", f"commit {D1[:12]}"),
            ("SOX-CM8", "High", f"commit {L1[:12]}"),  # a local merge pushed to main
            ("SOX-CM9", "High", "deployment 2 to Production EU"),
            ("SOX-EVD3", "Info", "branch main"),
            ("SOX-OPS1", "Medium", "workflow billing-close"),
            ("SOX-OPS3", "Low", "incident #40"),
            ("SOX-EVD2", "Medium", "workflow logs"),
        ]:
            self.assertIn(expected, got)
        self.assertNotIn(("SOX-CM8", "High", f"commit {R1[:12]}"), got)  # rebase-merged via PR 12
        self.assertFalse(any(F1 in str(c) for c in gh.calls))  # branch commit reached main via L1
        self.assertFalse(any("deployment 4" in e["item"] for e in pack.exceptions))  # outside the period
        self.assertFalse(any("staging" in e["item"] for e in pack.exceptions))  # filtered by --environment
        self.assertTrue(any(f"{E1[:12]}: PR lookup failed" in g for g in pack.gaps))
        self.assertEqual(pack.evidence["access"]["listing"]["admin"], ["boss"])
        self.assertEqual(pack.evidence["change"]["unsigned_commits"], 4)
        pr_call = next(c for c in gh.calls if isinstance(c, list) and c[0] == "pr")
        self.assertEqual(pr_call[pr_call.index("--base") + 1], "main")
        self.assertNotIn("Dev Person", json.dumps(pack.evidence))
        self.assertNotIn("dev@example.com", json.dumps(pack.evidence))

    def test_unreadable_protection_is_a_gap_not_a_finding(self):
        gh = full_fake(api={f"repos/{REPO}/branches/main/protection": sx.GhError("HTTP 403: Must have admin"),
                            f"repos/{REPO}/rules/branches/main": sx.GhError("HTTP 403")})
        pack = self.gather(gh)
        self.assertFalse(any(e["item"] == "branch main" and e["id"] != "SOX-EVD3" for e in pack.exceptions))
        self.assertTrue(any("branch controls not assessed" in g for g in pack.gaps))

    def test_unprotected_branch_is_assessed(self):
        gh = full_fake(api={f"repos/{REPO}/branches/main/protection": sx.GhError("HTTP 404: Branch not protected"),
                            f"repos/{REPO}/rules/branches/main": []})
        self.assertIn(("SOX-CM3", "High", "branch main"), ids(self.gather(gh)))

    def test_missing_permissions_become_gaps_not_crashes(self):
        pack = self.gather(FakeGh(api={f"repos/{REPO}": {}}), environment=None)
        self.assertTrue(any(g.startswith("access/collaborators: not gathered (HTTP 404") for g in pack.gaps))
        self.assertTrue(any("no matching GitHub environment" in g for g in pack.gaps))

    def test_repository_unreadable_raises(self):
        with self.assertRaises(sx.GhError):
            self.gather(FakeGh())

    def test_caps_are_reported(self):
        gh = full_fake(cli={"pr": [pr(n, reviews=[review("rev")], merge=f"q{n}") for n in range(sx.PRS_CAP)],
                            "issue": [{"number": n, "state": "OPEN"} for n in range(sx.INCIDENTS_CAP)]},
                       api={f"repos/{REPO}/actions/runs": [{"name": "ci", "conclusion": "success"}] * sx.RUNS_CAP})
        pack = self.gather(gh, max_lookups=0)
        for text in ("1000 PRs listed", "stopped PR lookups at 0", "at most 1000 runs", "500 issues listed"):
            self.assertTrue(any(text in g for g in pack.gaps), text)
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
        self.assertIn("| – | – | none | – |", sx.render_summary(sx.Pack(), REPO, SINCE, UNTIL, "now"))
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "pack"
            sx.write_pack(pack, out, text)
            manifest = (out / "MANIFEST.sha256").read_text().splitlines()
            self.assertEqual([m.split()[1] for m in manifest], ["access.json", "exceptions.json", "summary.md"])
            digest = hashlib.sha256((out / "summary.md").read_bytes()).hexdigest()
            self.assertIn(f"{digest}  summary.md", manifest)

    def test_main_writes_pack(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as out:
            code = sx.main(["--since", SINCE, "--until", UNTIL, "--out", tmp, "--environment", "Production EU",
                            "--bot", "approve-app"], gh=full_fake(), today=TODAY)
            self.assertEqual(code, 0)
            self.assertIn("SOX-CM9", (pathlib.Path(tmp) / "summary.md").read_text())
        self.assertIn("exceptions High:", out.getvalue())

    def test_main_default_out_is_outside_the_working_tree(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()), \
                mock.patch.object(sx.pathlib.Path, "home", return_value=pathlib.Path(tmp)):
            self.assertEqual(sx.main(["--since", SINCE, "--until", UNTIL], gh=full_fake(), today=TODAY), 0)
            self.assertTrue((pathlib.Path(tmp) / ".claude/security-reports/ledger/sox-evidence"
                             / f"{SINCE}_{UNTIL}" / "summary.md").exists())

    def test_main_exits_2_when_gh_cannot_read(self):
        with redirect_stderr(io.StringIO()) as err:
            self.assertEqual(sx.main(["--since", SINCE], gh=FakeGh(cli={"repo": sx.GhError("not a repo")})), 2)
        self.assertIn("cannot find the repository", err.getvalue())
        with redirect_stderr(io.StringIO()) as err:
            self.assertEqual(sx.main(["--since", SINCE, "--repo", REPO], gh=FakeGh()), 2)
        self.assertIn("gh auth status", err.getvalue())

    def test_bad_arguments(self):
        for argv in (["--since", "2026/01/01"], ["--since", "2026-02-30"], ["--since", "2026-05-01", "--until", "2026-04-01"],
                     ["--since", SINCE, "--repo", "bad repo"], ["--since", SINCE, "--environment", "x;y"],
                     ["--since", SINCE, "--incident-label", "a$b"], ["--since", SINCE, "--bot", "a&b"],
                     ["--since", SINCE, "--max-lookups", "-1"], []):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()):
                self.assertEqual(sx.main(argv, gh=FakeGh()), 2)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(sx.main(["--help"]), 0)


if __name__ == "__main__":
    unittest.main()
