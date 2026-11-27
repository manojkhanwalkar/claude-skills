# Re-checking open issues

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
