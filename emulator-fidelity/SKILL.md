---
name: emulator-fidelity
description: Find where a cloud emulator (AWS Emulator by default) differs from the real service, prove each against the provider's docs on the newest release, and file one public issue each, within a cap; --recheck closes verified fixes. Use to find, report or re-check emulator bugs. Not for testing the user's own code or security testing. Args - [SERVICES] [--cap N] [--report-only] [--version V] [--recheck].
license: Apache-2.0
---

# Emulator Fidelity

A local emulator is only as useful as it is faithful: when it accepts a request AWS refuses, or refuses one AWS accepts, tests pass locally and fail in the cloud. This skill finds such differences, proves each one, and reports it where the maintainers will fix it.

The value is in the evidence. An issue is worth filing only when it shows the emulator's exact response, links the AWS documentation that says what AWS does instead, and gives a short repro that a maintainer can paste into a terminal. A few precise issues help more than many vague ones; maintainers triage a flood from one account less carefully, and a duplicate of something they already track wastes their time.

It was written for [AWS Emulator](https://docs.aws.amazon.com/emulator/latest/userguide/) (`aws/aws-emulator`), and its commands use that product's layout. For another emulator, keep the method and rules and swap the setup.

## Arguments

- **SERVICES** (optional): the services to probe, for example `s3 dynamodb ecs`. Default: the commonly used ones listed in Phase 3.
- **`--cap N`**: the most issues to file in this run. With no cap given, ask; if the user leaves it to you, use 10 and say that it is your default.
- **`--report-only`**: do Phases 1–4 up to step 3 (confirmed and minimised), file nothing, and report the candidates with their draft issues.
- **`--version V`**: also reproduce on version V (for example the user's installed one: run the installed `aws-emulator` on your private port, never the user's). Filing always needs a reproduction on the newest release: the vendor's form asks whether it "still happens with the latest version".
- **`--recheck`**: instead of probing, re-run the user's own open issues on the newest release and close the ones that are fixed (see [Re-checking open issues](#re-checking-open-issues)). With `--report-only`, close and comment on nothing.

## Rules that always apply

- **Public, under the user's name, with their explicit consent.** Every issue is posted publicly from the user's GitHub account. Before the first filing, show the user the first issue's title and body and get an explicit yes for the repository, the cap and the format; after that, file the rest without asking each time. A background agent can't ask: its prompt must carry the user's confirmation of the repository, the cap and the format, or it runs with `--report-only`.
- **Nothing personal in issues.** No names, emails, account IDs, keys, hostnames, details of the user's projects, or home paths: write `~/.aws/emulator/<port>`, never `/home/<name>/...`.
- **Never touch the user's own emulator.** They may run one for daily work (a fixed port such as 9297, a systemd user unit, its `~/.aws/emulator/<port>` folder). Never stop, restart, reconfigure or send requests to it. Use your own ports.
- **Never call real AWS.** Point every command at your private emulator: set `AWS_ENDPOINT_URL`, `AWS_CONFIG_FILE` and `AWS_SHARED_CREDENTIALS_FILE` to that run's files, sign with that run's keys, and unset `AWS_PROFILE`. Real credentials must not be in the environment of any test command.
- **Memory and load.** Run at most two emulators at a time. Never run an emulator under a memory cap (`systemd-run -p MemoryMax=...`, `docker --memory`) or fill one until it is killed: a desktop reports every OOM kill as "application stopped, it was using too much memory", and users take that as their machine failing. No load, stress or DoS testing, no loops of thousands of requests, objects under 1 MiB. If a service starts real containers or processes (ECS tasks, Lambda runtimes), run one tiny one at a time, stop it at once, and compare `free -m` before and after. An extracted release takes about 1.4 GB, in RAM when the scratchpad is a tmpfs: keep one release at a time, and delete the package once it is extracted.
- **Functional fidelity only.** Compare API behaviour with AWS's documented behaviour. Don't try to break the emulator's security, escape its sandbox, or reach files or processes it shouldn't. If you notice something that looks like a vulnerability anyway (one caller reaching another's data, files outside the emulator's folder, an authentication bypass), stop exploring it, file nothing public, and tell the user. For AWS Emulator it goes to [AWS vulnerability reporting](https://aws.amazon.com/security/vulnerability-reporting/), the only private route its repository names (it has no private security advisories); for another emulator, its documented private channel. An existing public issue about it stays where it is; don't add exploit detail.
- **Clean up.** Stop every emulator you start by its PID (never `pkill -f <pattern>`, which can match your own shell). A clean stop deletes its `~/.aws/emulator/<port>` folder; if one is left, remove it with `rm -rf -- "$HOME/.aws/emulator/${PORT:?}"`, so an unset `PORT` can never reach the user's folders. Delete the downloaded package and the extracted tree at the end, kill GPG agents you started, and leave no background processes.

## Phase 1 – Set up the newest release, without installing it

Bugs are reported against the newest release, and the installed one may be older (the user's install is theirs to upgrade).

1. Find the newest version: the last entry of `curl -fsS https://downloads.aws.com/aws-emulator/packages/aws-emulator/LTS/versions.json` (entries look like `1.0.556.1`; `aws-emulator -v` prints `Version: 1.0.556`). The installed one: `aws-emulator -v`.
2. Download the package and its signature into an empty folder in the scratchpad, and verify them before using them. Use the package for the machine: `aws-emulator-x86_64.rpm` / `aws-emulator-aarch64.rpm`, or `aws-emulator_amd64.deb` / `aws-emulator_arm64.deb`.
   ```bash
   B=https://downloads.aws.com/aws-emulator/packages/aws-emulator/LTS/latest
   curl -fsSLo pkg.rpm "$B/aws-emulator-x86_64.rpm"; curl -fsSLo pkg.rpm.sig "$B/aws-emulator-x86_64.rpm.sig"
   curl -fsSLo key.asc https://downloads.aws.com/keys/gpg/current.asc
   export GNUPGHOME="$PWD/gnupg"; mkdir -m 700 "$GNUPGHOME"; gpg -q --import key.asc
   gpg --status-file status --verify pkg.rpm.sig pkg.rpm
   ok=; grep -aq '^\[GNUPG:\] VALIDSIG 98BCF336A3BE53B734E967C52E5BF49BD940F624 ' status && ok=1   # AWS's signing key
   gpgconf --kill all
   [ -n "$ok" ] || { echo "BAD signature: stop and tell the user"; exit 1; }
   ```
   Write the status to a file and grep that (`gpg --status-fd 1 | grep -q` can fail on a closed pipe), and keep `-a`: the status file holds binary notation data, and some greps (ugrep) then treat it as binary and find nothing. A failed check means stop, never skip the check.
3. Extract without installing, into `x/`, then delete the package:
   ```bash
   mkdir x && rpm2cpio pkg.rpm | (cd x && cpio -idm)     # or: dpkg -x pkg.deb x
   rm -f pkg.*
   x/opt/aws-emulator/bin/aws-emulator -v               # must print the newest version
   ```
   Run `x/opt/aws-emulator/bin/aws-emulator`. **Not** `x/usr/bin/aws-emulator`: in the rpm it is an absolute symlink to `/opt/aws-emulator/bin/aws-emulator`, the *installed* binary, so it silently runs the old version.
4. Start a private emulator on a port the user doesn't use (for example 9340–9349), with telemetry off and an idle timeout so a forgotten one stops by itself, and wait for it with a bound. Check first that nothing listens on the port and it has no folder: cleanup deletes `~/.aws/emulator/$PORT`, so a port that collides with the user's would delete their data.
   ```bash
   EMU=x/opt/aws-emulator/bin/aws-emulator; PORT=9340
   { [ -z "$(ss -Hltn "sport = :$PORT")" ] && [ ! -e ~/.aws/emulator/$PORT ]; } || { echo "port $PORT in use: pick another"; exit 1; }
   "$EMU" -p $PORT -t off --idle-timeout 600 > emu$PORT.log 2>&1 & echo $! > emu$PORT.pid
   D=~/.aws/emulator/$PORT
   ready=
   for i in $(seq 60); do
     curl -sf --cacert $D/ca.pem https://127.0.0.1:$PORT/__admin/health >/dev/null 2>&1 && { ready=1; break; }
     kill -0 "$(cat emu$PORT.pid)" 2>/dev/null || break      # it exited
     sleep 1
   done
   [ -n "$ready" ] || { echo "emulator on $PORT did not start:"; tail emu$PORT.log; kill "$(cat emu$PORT.pid)" 2>/dev/null; exit 1; }
   unset AWS_PROFILE AWS_SESSION_TOKEN
   export AWS_CA_BUNDLE=$D/ca.pem AWS_ENDPOINT_URL=https://127.0.0.1:$PORT AWS_DEFAULT_REGION=us-east-1 AWS_PAGER=""
   export AWS_CONFIG_FILE=$D/config AWS_SHARED_CREDENTIALS_FILE=$D/emulator_credentials
   export AWS_ACCESS_KEY_ID=$(awk -F' *= *' '/aws_access_key_id/{print $2}' $D/emulator_credentials)
   export AWS_SECRET_ACCESS_KEY=$(awk -F' *= *' '/aws_secret_access_key/{print $2}' $D/emulator_credentials)
   ```
   The keys work only for that run. The account is always `000000000000`. The AWS CLI v2 is enough for most repros. When the CLI hides the response, sign a raw request with curl:
   `curl -s --cacert $D/ca.pem --aws-sigv4 "aws:amz:us-east-1:sqs" --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" ... https://127.0.0.1:$PORT/`.

## Phase 2 – Know what is already known

Read these before probing, so you don't report what the vendor already documents or tracks:

- **Documented limitations:** the user guide's [fidelity](https://docs.aws.amazon.com/emulator/latest/userguide/fidelity.html), [Security](https://docs.aws.amazon.com/emulator/latest/userguide/security.html) and [check-project](https://docs.aws.amazon.com/emulator/latest/userguide/check-project.html) pages, and its service list. A documented limitation is not a bug (for example: AWS Emulator does not evaluate IAM the way AWS does, and runs Lambda code unisolated with the user's permissions).
- **The vendor's known-gaps list.** AWS Emulator tracks thousands of known differences as files in its repository, not as GitHub issues: `issues/things-that-do-not-work/` (and `issues/things-that-now-work/` once fixed). Its README's "Known issues" section points there. Search the file names by service and operation before filing anything:
  ```bash
  # List the folder itself: the whole-repository tree is too big and comes back truncated.
  gh api "repos/aws/aws-emulator/git/trees/main:issues/things-that-do-not-work" --jq '.truncated, (.tree[].path)' > known.txt
  head -1 known.txt                                   # must be false; if true, the list is incomplete
  grep -iE '(puttargets|inputpath)' known.txt         # then read the matching files
  ```
  A match means the gap is known: don't file it (you may add a comment to an existing GitHub issue if your case adds something new). Missing this step is how duplicates get filed.
- **Release notes:** each release lists the gaps it fixed; check them when the installed and newest versions differ.
- **The vendor's fidelity scores** (per service, tests passed of the total): a low-scoring service is likely to have known gaps.
- **GitHub issues, open and closed:** `gh search issues -R aws/aws-emulator "<keywords>"` before each filing, and `gh issue list -R aws/aws-emulator --state all --limit 2000` for a full list (the repository has hundreds). If an issue covers the same root cause, comment on it with your new cases instead of filing a new one.

## Phase 3 – Probe

Work service by service, the commonly used ones first, unless the user names services: S3, DynamoDB, SQS, SNS, Lambda, IAM, STS, Secrets Manager, SSM Parameter Store, KMS, EventBridge (and Scheduler), CloudWatch Logs, Step Functions, Kinesis, CloudFormation, API Gateway (REST, HTTP, WebSocket), ECS, Cognito.

Aim at behaviour the API reference states precisely, where a difference would change what tested code does. The kinds of difference that turned out to be real, with examples:

| Kind | Examples |
|---|---|
| **Validation the emulator skips** (the most common kind) | S3 CORS wildcards (one `*` per origin); Step Functions `Retry` ranges; ECS task definitions (an essential container, the name pattern, links only with `bridge`, mount points naming real volumes, health-check ranges, container memory within the task's, Fargate `stopTimeout` ≤ 120, `DAEMON` not on Fargate); Cognito email format, auth-flow names, a default redirect URI from the callback list; API Gateway authorization types, the TOKEN authorizer identity source, the HTTP API route selection expression, the WebSocket payload version |
| **Validation the emulator adds** | EventBridge `PutRule` refusing valid cron `L`, `W` and `#` (while Scheduler accepts them) |
| **Lifecycle and timing rules** | SQS `QueueDeletedRecently` within 60 s; Lambda runtimes past their block-create date still accepted |
| **Scoping** | Resources that should be per Region or per account but are shared (CloudWatch Logs log groups were shared across Regions) |
| **Authorization consistency** | One operation of a service enforcing IAM while a sibling does not (SQS `ListQueues` vs `GetQueueUrl`); file only as an inconsistency, since full IAM fidelity is a documented non-goal |
| **Unimplemented paths** | An operation answering `501 NotImplemented` for a documented, common use (SNS `Publish` to a phone number) |
| **Failing late instead of early** | A create call accepting what a later call can never use (Lambda functions on runtimes the emulator can't run: refuse at `CreateFunction`, and answer with a 4xx so SDKs don't retry a 502) |

Also worth checking: error codes and HTTP status (SDKs branch on them), pagination and continuation tokens, conditional writes, `ReturnValues`, waiters, ARN and ID formats, default values, limits (item size, name length), and ordering guarantees.

Not worth filing: wording differences in error messages (unless code commonly parses them), and anything whose AWS behaviour you can't find documented. Real AWS may well differ there too, but without a document or an account to test against it is a guess: list those in the final report as "checked, not filed: AWS behaviour not documented".

## Phase 4 – Confirm and file, one at a time

Take each candidate all the way through before testing the next area. Don't collect a batch and file at the end: the user wants each issue as soon as it is confirmed, and a session can end early (usage limits) with nothing filed.

1. **Document AWS's behaviour:** find the API reference or user guide page that states it, and keep the URL.
2. **Check it isn't known** (Phase 2): the known-gaps files, then GitHub issues.
3. **Reproduce twice on fresh emulator runs of the newest release** (and on `--version` V if given), with identical results. Minimise to the shortest CLI or curl commands that show it, starting from an emulator start.
4. **File it as its own issue** (skip with `--report-only`). One difference per issue; cases that share one API's validation may share an issue. Use the format below with `gh issue create -R aws/aws-emulator --title ... --body-file ...`.
5. **Tell the user** in one line: the issue number, title, link and the running count. Then check it rendered: open, links present, no personal paths (`gh issue view <n> --json body`).

Stop when you reach the cap or run out of solid findings, whichever comes first. Never lower the bar to reach the cap.

### Issue format

`gh issue create --body-file` bypasses the repository's issue form (`.github/ISSUE_TEMPLATE/behavior-differs.yml`), so write the body with the form's sections, in its order, all of them filled in. Title: `<Service>: <what differs>`, specific enough to triage from the list, for example `SQS: CreateQueue with the name of a queue deleted less than 60 seconds ago succeeds instead of failing with QueueDeletedRecently`.

````markdown
### Before you file

- [x] I searched open and recently closed issues and found no report of this.
- [x] I checked that this still happens with the latest version of the emulator.

### What happened

<the emulator's response: status, error code, message and the relevant fields, in a code block>

### What you expected

As on AWS: <behaviour>, per the [<API name> reference](<docs URL>).

### Steps to reproduce

Freshly started emulator, default settings except telemetry, Linux x86_64, AWS CLI <version>:

```bash
aws-emulator -p 9332 -t off &
D=~/.aws/emulator/9332
until curl -sf --cacert $D/ca.pem https://127.0.0.1:9332/__admin/health >/dev/null 2>&1; do sleep 1; done
export AWS_CA_BUNDLE=$D/ca.pem AWS_ENDPOINT_URL=https://127.0.0.1:9332 AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=$(awk -F' *= *' '/aws_access_key_id/{print $2}' $D/emulator_credentials)
export AWS_SECRET_ACCESS_KEY=$(awk -F' *= *' '/aws_secret_access_key/{print $2}' $D/emulator_credentials)

<commands, with the result of each as a trailing comment>
```

Reproduced on fresh runs.

### Emulator version

```
<the output of aws-emulator -v for the newest release; also any older version it reproduces on>
```

### Impact and workaround

<who it affects and how: what tested code would get wrong; any workaround>

### Additional context

<anything else: a related behaviour in the same emulator that is correct, related issues>
````

Where the emulator is inconsistent with itself (Scheduler accepts a cron expression that EventBridge `PutRule` refuses; DynamoDB is regional but log groups are not), say so under Additional context: it shows the fix is local and makes the report easier to accept.

## Re-checking open issues

With `--recheck`, the job is to keep the user's issues honest, not to find new ones. Phase 1 as usual (the newest release, a private emulator), then:

1. **List the user's open issues:** `gh issue list -R aws/aws-emulator --author @me --state open --limit 200 --json number,title,body,url`. Read each one's comments too (`gh issue view <n> --comments`): a maintainer may have asked a question, named a fix version or marked it as working as intended. Answer nothing on the user's behalf; list such replies in the report.
2. **Re-run each repro on a fresh private emulator of the newest release.** The issue body starts `aws-emulator` on its own port: substitute `$EMU` and your private port, never the binary on `PATH` (the installed, possibly older one) or the user's port. Run every case in the issue, not only the first.
3. **Classify** each issue: **fixed** (every case now matches the AWS behaviour the issue cites, confirmed on two fresh runs), **partly fixed** (some cases fixed, some not), or **still broken**.
4. **Act, one issue at a time:**
   - *Fixed:* close it with a comment: `gh issue close <n> -R aws/aws-emulator --comment "Verified fixed in <aws-emulator -v>: <the repro's new result, in a code block>"`.
   - *Partly fixed:* leave it open and add one comment saying which cases now pass and which still fail, with the version.
   - *Still broken:* leave it open, with no comment (a "still happens" comment on every issue is noise; the vendor's form already asked about the latest version).
   - Closing and commenting are public actions under the user's name: show the first close comment and get a yes, as for filing. A background agent without that confirmation runs as `--report-only`.
5. **Clean up** as the rules above say, between issues and at the end.

Report a table: issue number and link, title, status (closed as fixed, partly fixed, still broken), the version checked, and any maintainer reply that needs the user. Then the cleanup line from the final report.

## Running it in the background

A full pass takes hours. Run it in a background agent with this skill's rules in its prompt, plus the user's confirmed repository, cap and format, and keep working with the user:

- **One progress signal:** the agent's own message per filing (number, title, link, running count) is the signal; relay each to the user once. Don't add a monitor that also watches the issue list: it reports every filing twice. The agent itself checks `journalctl --user --since "<its start time>" | grep -c oom-kill` after each probe that starts containers or processes, and stops and reports if the count rises.
- **Steering:** pass the user's changes (cap, scope, "file each immediately") to the agent with a message; it applies them at its next step.
- **Usage limits:** an agent that stops on a rate limit keeps its work; resume it with a message once the limit resets, instead of starting a new one.

## Final report

- A table of the issues filed: number and link, service, the difference in one line; and the running total for the user.
- Comments added to existing issues.
- Checked and not filed, one line each: matched AWS; already known (the known-gaps file or issue number); documented limitation; AWS behaviour not documented (what a test against real AWS would settle).
- Anything security-looking, kept out of public issues, with the private route.
- Cleanup: emulators stopped, folders removed (`ls ~/.aws/emulator/` shows only the user's own), package and extracted tree deleted, no processes left.
