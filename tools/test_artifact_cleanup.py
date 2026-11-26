"""Tests for templates/artifact-cleanup.yml: its delete step runs against a stub `gh`, and this repo's
own copy matches the template apart from the `workflows:` list."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "artifact-cleanup.yml"
COPY = ROOT / ".github" / "workflows" / "artifact-cleanup.yml"


def artifact(id_, run, branch="main", name="coverage", expired=False):
    return (f'{{"id":{id_},"name":"{name}","expired":{str(expired).lower()},'
            f'"workflow_run":{{"id":{run},"head_repository_id":5,"head_branch":"{branch}"}}}}')


# The stub answers the listing, one status per run id, and deletes; it logs each delete it accepts.
STUB = """#!/usr/bin/env bash
case "$*" in
  *"actions/artifacts?per_page"*) cat <<'J'
{artifacts}
J
  ;;
  *"runs/10"*) echo completed;;
  *"runs/20"*) echo in_progress;;
  *"runs/30"*) echo completed;;
  *"runs/12"*) echo "gh: Not Found (HTTP 404)" >&2; exit 1;;
  *"runs/13"*) echo "gh: Server Error (HTTP 502)" >&2; exit 1;;
  *"-X DELETE"*"artifacts/5") echo "gh: Not Found (HTTP 404)" >&2; exit 1;;
  *"-X DELETE"*) echo "${{@: -1}}" >> "$DELETED"; exit 0;;
  *) echo "unexpected: $*" >&2; exit 2;;
esac
"""


@unittest.skipUnless(shutil.which("jq") and shutil.which("bash"), "needs jq and bash")
class ArtifactCleanupTest(unittest.TestCase):

    def run_step(self, artifacts):
        script = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))["jobs"]["cleanup"]["steps"][0]["run"]
        with tempfile.TemporaryDirectory() as tmp:
            gh = Path(tmp) / "gh"
            gh.write_text(STUB.format(artifacts="\n".join(artifacts)), encoding="utf-8")
            gh.chmod(0o755)
            deleted = Path(tmp) / "deleted"
            deleted.touch()
            env = {**os.environ, "PATH": f"{tmp}:{os.environ['PATH']}", "REPO": "o/r", "DELETED": str(deleted)}
            result = subprocess.run(["bash", "-c", script], cwd=tmp, env=env, capture_output=True, text=True,
                                    timeout=60)
            ids = sorted(int(line.rsplit("/", 1)[1]) for line in deleted.read_text().split())
        return result, ids

    def test_keeps_the_newest_run_per_kind_and_branch_and_only_deletes_finished_runs(self):
        result, deleted = self.run_step([
            artifact(1, 10), artifact(2, 20), artifact(3, 30),     # main: 30 newest; 10 done; 20 running
            artifact(4, 11, branch="feat"),                        # the only one on its branch: kept
            artifact(5, 12, name="img~abc.dockerbuild"),           # run gone (404); artifact already gone
            artifact(6, 31, name="img~zz9.dockerbuild"),           # newest build record: kept
            artifact(7, 13),                                       # run lookup failed (502): kept
            artifact(8, 9, expired=True),                          # expired: ignored
        ])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([1], deleted)
        self.assertIn("already gone: img~abc.dockerbuild (main, run 12)", result.stdout)
        self.assertIn("::warning::could not look up run 13", result.stdout)
        self.assertIn("deleted 1, skipped 2", result.stdout)

    def test_repo_copy_matches_the_template_except_its_workflows_list(self):
        def body(path):
            return [line for line in path.read_text(encoding="utf-8").splitlines()
                    if not line.strip().startswith("workflows:")]
        self.assertEqual(body(TEMPLATE), body(COPY))


if __name__ == "__main__":
    unittest.main()
