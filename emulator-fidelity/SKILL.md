---
name: emulator-fidelity
description: Find places where a local cloud emulator (AWS Emulator by default) behaves differently from the real service, prove each one against the provider's documentation with a short repro on the newest release, and report it as one public GitHub issue per difference on the emulator's repository, filed as soon as it is confirmed - so the emulator gets fixed for everybody. Covers getting and verifying the latest release without installing it, safe private emulators (memory-bounded, cleaned up, never touching the user's running one), which services and edge cases to probe, what counts as a bug and what does not (documented limitations, undocumented AWS behaviour, duplicates), the issue format, an issue cap, and routing anything security-sensitive to private disclosure instead. Use when the user asks to find, probe, test or report bugs, gaps, discrepancies or fidelity problems in AWS Emulator (or another emulator of a cloud API), or to file a gap found while building against it. Not for testing the user's own code against an emulator (use its tests) or for security testing of the emulator. Args - optional service list (default the commonly used ones), optional --cap N (default 10, ask first), optional --report-only to list candidates without filing, optional --version V (default the newest release).
---

# Emulator Fidelity

A local emulator is only as useful as it is faithful: when it accepts a request AWS refuses, or refuses one AWS accepts, tests pass locally and fail in the cloud. This skill finds such differences, proves each one, and reports it where the maintainers will fix it.

The value is in the evidence. An issue is worth filing only when it shows the emulator's exact response, links the AWS documentation that says what AWS does instead, and gives a short repro that a maintainer can paste into a terminal on a fresh emulator. A few precise issues help more than many vague ones; maintainers triage a flood from one account less carefully.

It was written for [AWS Emulator](https://docs.aws.amazon.com/emulator/latest/userguide/) (`aws/aws-emulator`), and its commands use that product's layout. For another emulator, keep the method and rules and swap the setup.

## Rules that always apply

- **Public, under the user's name.** Every issue is posted publicly from the user's GitHub account. Before the first filing in a session, confirm that the user wants issues filed (a request like "find and report bugs" counts), which repository, and the cap. Write nothing about the user, their projects, machine, paths (`~/.aws/emulator/<port>`, never `/home/<name>/...`), hostnames, account IDs or keys.
- **Never touch the user's own emulator.** They may run one for daily work (a fixed port such as 9297, a systemd user unit, its `~/.aws/emulator/<port>` folder). Never stop, restart, reconfigure or send requests to it. Use your own ports.
- **Never call real AWS.** Always set `AWS_ENDPOINT_URL` to your private emulator and sign with that run's keys. Real credentials must not be in the environment of any test command.
- **Memory and load.** Run at most two emulators at a time. Never run an emulator under a memory cap (`systemd-run -p MemoryMax=...`, `docker --memory`) or fill one until it is killed: a desktop reports every OOM kill as "application stopped, it was using too much memory", and users take that as their machine failing. No load, stress or DoS testing; no loops of thousands of requests; objects under 1 MiB. If a service starts real containers or processes (ECS tasks, Lambda runtimes), run one tiny one at a time, stop it at once, and compare `free -m` before and after.
- **Functional fidelity only.** Compare API behaviour with AWS's documented behaviour. Don't try to break the emulator's security, escape its sandbox, or reach files or processes it shouldn't. If you notice something that looks like a vulnerability anyway (one caller reaching another's data, files outside the emulator's folder, an authentication bypass), stop exploring it, file nothing public, and tell the user: it goes to the vendor privately ([AWS vulnerability reporting](https://aws.amazon.com/security/vulnerability-reporting/), or the repository's private security advisory). An existing public issue about it stays where it is; don't add exploit detail.
- **Clean up.** Stop every emulator you start (by its PID, never `pkill -f <pattern>`, which can match your own shell), remove its `~/.aws/emulator/<port>` folder, and leave no background processes, GPG agents or temporary files outside the scratchpad.

## Phase 1 – Set up the newest release, without installing it

Bugs are reported against the newest release, and the installed one may be older (the user's install is theirs to upgrade).

1. Find the newest version: `curl -fsS https://downloads.aws.com/aws-emulator/packages/aws-emulator/LTS/versions.json` (the last entry), and the installed one with `aws-emulator -v`.
2. Download the package and its signature into an empty folder in the scratchpad, and verify it before using it:
   ```bash
   B=https://downloads.aws.com/aws-emulator/packages/aws-emulator/LTS/latest
   curl -fsSLo pkg.rpm "$B/aws-emulator-x86_64.rpm"; curl -fsSLo pkg.rpm.sig "$B/aws-emulator-x86_64.rpm.sig"   # or aws-emulator_amd64.deb(.sig)
   curl -fsSLo key.asc https://downloads.aws.com/keys/gpg/current.asc
   export GNUPGHOME="$PWD/gnupg"; mkdir -m 700 "$GNUPGHOME"; gpg -q --import key.asc
   gpg --status-file status --verify pkg.rpm.sig pkg.rpm
   grep -q "VALIDSIG 98BCF336A3BE53B734E967C52E5BF49BD940F624" status && echo signature OK   # AWS's signing key
   ```
   Write the status to a file and grep it (`gpg --status-fd 1 | grep -q` can fail on a closed pipe). Kill the GPG agent afterwards (`gpgconf --kill all` with the same `GNUPGHOME`).
3. Extract without installing: `rpm2cpio pkg.rpm | cpio -idm` (or `dpkg -x pkg.deb x/`). Run `x/opt/aws-emulator/bin/aws-emulator`. **Not** `x/usr/bin/aws-emulator`: it is an absolute symlink to the *installed* binary, so it silently runs the old version. Check with `-v`.
4. Start a private emulator on a fixed port the user doesn't use (for example 9340–9349), with telemetry off and an idle timeout so a forgotten one stops by itself:
   ```bash
   EMU=x/opt/aws-emulator/bin/aws-emulator; PORT=9340
   "$EMU" -p $PORT -t off --idle-timeout 600 > emu$PORT.log 2>&1 & echo $! > emu$PORT.pid
   D=~/.aws/emulator/$PORT
   until curl -sf --cacert $D/ca.pem https://127.0.0.1:$PORT/__admin/health >/dev/null 2>&1; do sleep 1; done
   export AWS_CA_BUNDLE=$D/ca.pem AWS_ENDPOINT_URL=https://127.0.0.1:$PORT AWS_DEFAULT_REGION=us-east-1 AWS_PAGER=""
   export AWS_ACCESS_KEY_ID=$(awk -F' *= *' '/aws_access_key_id/{print $2}' $D/emulator_credentials)
   export AWS_SECRET_ACCESS_KEY=$(awk -F' *= *' '/aws_secret_access_key/{print $2}' $D/emulator_credentials)
   ```
   The keys work only for that run. The account is always `000000000000`. The AWS CLI v2 is enough for most repros; `curl --aws-sigv4 "aws:amz:us-east-1:<service>"` signs raw requests when the CLI hides the response.

## Phase 2 – Know what is already known

Read these before probing, so you don't report what the vendor already says or someone already filed:

- The emulator's documented limitations: the user guide's supported-services, limitations, fidelity and Security pages. A documented limitation is not a bug (for example: AWS Emulator does not evaluate IAM the way AWS does and runs Lambda code unisolated with the user's permissions).
- The vendor's own fidelity results, if published (AWS Emulator publishes per-operation scores for each release). An operation with known failing tests may still deserve an issue if your case is specific, but say so.
- Existing issues, open and closed: `gh issue list -R aws/aws-emulator --state all --limit 500 --json number,title,state`, and `gh search issues -R aws/aws-emulator "<keywords>"` before each filing. If an existing issue covers the same root cause, add a comment with your new cases instead of a new issue.

## Phase 3 – Probe

Work service by service, the commonly used ones first, unless the user names services: S3, DynamoDB, SQS, SNS, Lambda, IAM, STS, Secrets Manager, SSM Parameter Store, KMS, EventBridge (and Scheduler), CloudWatch Logs, Step Functions, Kinesis, CloudFormation, API Gateway (REST, HTTP, WebSocket), ECS, Cognito.

Aim at behaviour the API reference states precisely, where a difference would change what tested code does:

| Kind | Examples that found real differences |
|---|---|
| **Validation the emulator skips** (the most common kind) | IAM policy grammar (action without a service prefix, `Action` with `NotAction`, unknown elements and condition operators); S3 CORS wildcards (one `*` per origin); EventBridge targets with both `Input` and `InputPath`; Step Functions `Retry` ranges; ECS task-definition rules (an essential container, name pattern, links only with `bridge`, mount points naming real volumes, health-check ranges, container memory within the task's, Fargate `stopTimeout` ≤ 120, `DAEMON` not on Fargate); Cognito email format, auth-flow names, default redirect URI in the callback list; API Gateway authorization types, TOKEN authorizer identity source, HTTP API route selection expression, WebSocket payload version |
| **Validation the emulator adds** | EventBridge `PutRule` refusing valid cron `L`, `W` and `#` (while Scheduler accepts them) |
| **Lifecycle and timing rules** | SQS `QueueDeletedRecently` within 60 s; Lambda runtimes past their block-create date still accepted |
| **Scoping** | Resources that should be per Region or per account but are shared (CloudWatch Logs log groups were shared across Regions) |
| **Authorization consistency** | One operation of a service enforcing IAM while a sibling does not (SQS `ListQueues` vs `GetQueueUrl`) - file only as an inconsistency, since full IAM fidelity is a documented non-goal |
| **Unimplemented paths** | An operation answering `501 NotImplemented` for a documented, common use (SNS `Publish` to a phone number) |
| **Fail late instead of early** | A create call accepting what a later call can never use (Lambda functions on runtimes the emulator can't run: refuse at `CreateFunction`, and answer with a 4xx so SDKs don't retry a 502) |

Also worth checking: error codes and HTTP status (SDKs branch on them), pagination and continuation tokens, conditional writes, `ReturnValues`, waiters, ARN and ID formats, default values, limits (item size, name length), and ordering guarantees.

Not worth filing: wording differences in error messages (unless code commonly parses them), and anything where you can't find AWS's documented behaviour. Real AWS may well differ there too, but without a document or an account to test against, it is a guess: list those in the final report as "checked, not filed: AWS behaviour not documented".

## Phase 4 – Confirm and file, one at a time

Take each candidate all the way through before testing the next area. Don't collect a batch and file at the end: the user wants each issue as soon as it is confirmed, and a session can end early (usage limits) with nothing filed.

1. **Document AWS's behaviour:** find the API reference or user guide page that states it, and keep the URL.
2. **Search for duplicates** (Phase 2). Comment on an existing issue instead of filing a new one when it covers the same root cause.
3. **Reproduce twice on fresh emulator runs of the newest release** (and, if installed, the user's version), with identical results. Minimise to the shortest CLI or curl commands that show it, starting from an emulator start.
4. **File it as its own issue.** One difference per issue; cases that share one API's validation may share an issue. Use the format below, `gh issue create -R aws/aws-emulator --title ... --body-file ...`.
5. **Tell the user** in one line: the issue number, title and link. Then check it rendered: open, links present, no personal paths (`gh issue view <n> --json body`).

Stop when you reach the cap or run out of solid findings, whichever comes first. Never lower the bar to reach the cap.

### Issue format

Title: `<Service>: <what differs>` - specific enough to triage from the list, for example `SQS: CreateQueue with the name of a queue deleted less than 60 seconds ago succeeds instead of failing with QueueDeletedRecently`.

```markdown
### Before you file

- [x] I searched open and recently closed issues and found no report of this.
- [x] I checked that this still happens with the latest version of the emulator (<version>, the newest package in `LTS/versions.json`; also seen on <older version>).

### What happened

<the emulator's response: status, error code, message, the relevant fields, in a code block>

### What you expected

As on AWS: <behaviour>, per the [<API name> reference](<docs URL>). <why it matters to someone testing against the emulator, in one sentence>

### Steps to reproduce

Freshly started emulator, default settings except telemetry, Linux x86_64, AWS CLI <version>:

```bash
aws-emulator -p 9332 -t off &
D=~/.aws/emulator/9332
export AWS_CA_BUNDLE=$D/ca.pem AWS_ENDPOINT_URL=https://127.0.0.1:9332 AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=$(awk -F' *= *' '/aws_access_key_id/{print $2}' $D/emulator_credentials)
export AWS_SECRET_ACCESS_KEY=$(awk -F' *= *' '/aws_secret_access_key/{print $2}' $D/emulator_credentials)

<commands, with the result of each as a trailing comment>
```

Reproduced on fresh runs of <version> (and <older version>).
```

Where the emulator is inconsistent with itself (Scheduler accepts a cron expression that EventBridge `PutRule` refuses; DynamoDB is regional but log groups are not), say so: it shows the fix is local and makes the report easier to accept.

## The cap

Ask the user for a cap before filing, or use 10 and **say that it is your default**, not theirs. Report the running count after each filing (this round and in total) and stop at the cap; the user may raise it. A cap keeps the issues to the strongest findings and the run bounded.

## Running it in the background

A full pass takes hours. Run it in a background agent with this skill's rules in its prompt, and keep working with the user:

- **Watch, don't poll:** a monitor that lists the user's issues on the repository every minute and prints new ones, and counts `oom-kill` lines in `journalctl --user` since it started. Parse with `jq '.[] | ...'`, not `.[0] | ...`, which prints `null null` for an empty list and looks like a result.
- **Relay each filing** to the user once (the agent's message and the monitor event are the same issue).
- **Steering:** pass the user's changes (cap, scope, "file each immediately") to the agent with a message; it applies them at its next step.
- **Usage limits:** an agent that stops on a rate limit keeps its work; resume it with a message once the limit resets, instead of starting a new one.

## Final report

- A table of the issues filed: number and link, service, the difference in one line; and the running total for the user.
- Comments added to existing issues.
- Checked and not filed, one line each: matched AWS; AWS behaviour not documented (what a test against real AWS would settle); already reported (by number); documented limitation.
- Anything security-looking, kept out of public issues, with the recommended private route.
- Cleanup: emulators stopped, folders removed (`ls ~/.aws/emulator/` shows only the user's own), no processes left.
