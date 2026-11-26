# Directory submission: `manoj-skills`

This page prepares the `manoj-skills` plugin for [Anthropic's plugin directory](https://claude.ai/directory). The owner submits it from the developer portal at [claude.ai/directory/manage](https://claude.ai/directory/manage) on a paid claude.ai plan. Nothing here submits anything.

Sources (read 2026-11-26):

- [Publish and distribute a plugin](https://code.claude.com/docs/en/plugins/publish.md), the section "Submit to Anthropic's directory" (abbreviated **[publish]** below).
- [Submit your plugin](https://claude.com/docs/plugins/submit) (**[submit]**).
- [Plugin pre-submission checklist](https://claude.com/docs/plugins/pre-submission-checklist) (**[checklist]**).
- [Plugin manifest reference](https://code.claude.com/docs/en/plugins/manifest-reference.md) (**[manifest]**).
- [Plugin feature support across platforms](https://claude.com/docs/plugins/platform-support) (**[platforms]**).

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Manifest | Add `.claude-plugin/plugin.json` | The directory reads a folder that contains `.claude-plugin/plugin.json`; without one, validation blocks with **No plugin.json** [checklist]. It also sets `description`, `author`, `homepage` and `repository` [publish, step 5]. |
| Where the skills are listed | In `plugin.json` (`skills`: the 27 folders, as `./<dir>`) | The directory reads `plugin.json`, not the marketplace entry. `skills` accepts folders that each hold a `SKILL.md` [manifest]. |
| `strict` in `marketplace.json` | Removed (defaults to `true`), along with the entry's `skills` list | With a `plugin.json` present, `strict: false` plus a `skills` list in the entry fails to load with "conflicting manifests", and with `strict: true` the entry's skills are appended to the manifest's, which would list each skill twice [manifest, "How entry fields combine"]. The entry keeps the same `name` as `plugin.json` [publish]. |
| Version | `1.0.0` at first submission (now `1.1.0`), raised in every PR that changes what the plugin ships | Once `version` is set, users stay on it until it changes; the alternative is to omit it and track the commit SHA, which makes `validate --strict` fail on the missing `version` [publish, step 2 and 3]. The directory says "If your `plugin.json` sets `version`, raise it with every release" [submit]. CI enforces the raise. |
| Icon | `.claude-plugin/icon.png` (512 x 512 PNG), named in `icon` | `validate` warns `ICON_MISSING`, and the icon becomes the listing icon only the first time the plugin is saved or submitted in the portal, so it has to be there before the first submission. |
| Listing links | `supportUrl` (GitHub issues), `documentationUrl` (README), `privacyPolicyUrl` (README privacy section) | Directory listing fields that only `plugin.json` may carry [manifest]. No email in the repository: the portal asks for the contact email itself. |
| What to submit | The whole plugin, described as built for Claude Code | See [Surface compatibility](#surface-compatibility). |

## Validation

`claude plugin validate --strict .` (Claude Code 2.1.332 locally, and 2.1.319 as pinned in CI) on the PR branch:

```text
Validating marketplace manifest: .../.claude-plugin/marketplace.json
Provides:
  ❯ skills: manoj-skills:ada-compatibility
  ... (27 skills)
Hosts not read for: skills (27)
Plugin directory checks for ...
  ❯ This folder also holds a marketplace manifest. The plugin directory treats such a folder as a
    plugin, so these checks cover only the plugin in this folder.
✔ These checks found nothing to report
The directory also runs a safety scan and a policy review that this command does not.
✔ Validation passed
```

The first run with `plugin.json` reported one directory warning, `ICON_MISSING`, fixed by the icon. An install from a local marketplace into an empty config (`claude plugin marketplace add <repo>`, `claude plugin install manoj-skills@manoj-claude-skills`) reports `manoj-skills@manoj-claude-skills`, version `1.0.0`, enabled, no errors.

## Pre-submission checklist

Every row of [checklist] with its result for this repository. The plugin folder is the repository root.

**Summary: 27 pass, 0 fail, 15 not applicable, 2 open for the owner (the portal's name check and a `claude plugin eval` comparison). No blocker.**

### Repository and folder layout

| Check | Result | Evidence |
|---|---|---|
| A folder with `.claude-plugin/plugin.json` | Pass | Added at the repository root. |
| One plugin per submission | Pass | `marketplace.json` lists one plugin, `source: "./"`; submit the root once. |
| Every file a hook, MCP server or script uses is inside the plugin; no `..` in `plugin.json` paths | Pass | All `skills` paths are `./<dir>`; scripts are called through `${CLAUDE_SKILL_DIR}` and shared files through `${CLAUDE_SKILL_DIR}/../CONVENTIONS.md`, inside the root. |
| No symbolic links, submodules or Git LFS pointers | Pass | `git ls-files` has no links; no `.gitmodules`; no `.gitattributes`. |
| No `.DS_Store`, `Thumbs.db`, `desktop.ini`, `__MACOSX` | Pass | None tracked. |
| File names valid on Windows and macOS, no case-only clashes | Pass | No colons, trailing dots or spaces, device names, or case-folded duplicates. |
| Folder names on the path to the plugin | N/A | The plugin is the repository root. |
| No `export-ignore`, `export-subst` or content filters in `.gitattributes` | Pass | No `.gitattributes`. |
| Repository under 50 MiB archived and 256 MiB unpacked, under 10,000 files, each file under 5 MiB | Pass | About 105 files; the largest is `README.md` at about 60 KB. |

### Manifest and plugin name

| Check | Result | Evidence |
|---|---|---|
| `name` is lowercase letters, digits and hyphens, up to 64 characters | Pass | `manoj-skills`. |
| Not a reserved or generic name, not presented as official | Pass | Built on the author's name; no `claude`, `anthropic`, `official`, `plugin`, `mcp` or `test`. |
| No other organization's plugin uses the name | Open | Only the portal can check; nothing found under that name. |
| Name, `displayName` and `author.name` can't be mistaken for a brand | Pass | `Manoj Skills`, `Manoj Khanwalkar`. One skill is called `mcp-builder`, like Anthropic's example skill; it is namespaced as `manoj-skills:mcp-builder` and its description says it hands Python and TypeScript to Anthropic's skill, so it does not pose as it. |
| A fork has its own name | N/A | Not a fork. |
| `displayName` and `author.name` in one writing system | Pass | Plain ASCII. |
| Component keys spelled as in the reference | Pass | Only `skills` and `icon`; `validate --strict` passes. |
| `description`, `author` and `version` set | Pass | 208-character description, author name and GitHub URL (no email), `1.0.0`. |

### README and license

| Check | Result | Evidence |
|---|---|---|
| README of 40 or more words outside code blocks | Pass | `README.md`, thousands of words. |
| `LICENSE` file or `license` field | Pass | `LICENSE` (Apache 2.0), `NOTICE`, and `license: Apache-2.0` in `plugin.json`. |

### Files in the plugin folder

| Check | Result | Evidence |
|---|---|---|
| Non-image files under 256 KiB | Pass | Largest about 60 KB. |
| 512 files or fewer | Pass | About 105. |
| Only text, complete PNG/JPEG/GIF/WebP images and fonts | Pass | All text, plus `.claude-plugin/icon.png`. |
| Bundled images shown only through Markdown, never from commands, hooks or scripts | Pass | The icon is referenced only by `plugin.json`'s `icon`. |
| MCP servers declared with `command`/`args` or `url`, not bundles | N/A | No MCP servers. |

### What the plugin runs and connects to

| Check | Result | Evidence |
|---|---|---|
| Launchers pinned to exact versions | N/A | No hooks or MCP servers run a launcher. The one `npx` a skill suggests (`ada-compatibility`, axe or pa11y, only if the user agrees) now says to pin an exact version published at least two weeks earlier. |
| No package-manager config that sets a registry | N/A | No `.npmrc`, `bunfig.toml` or `uv.toml`. |
| No real credentials in any file | Pass | Gitleaks runs on every PR and push and weekly over the whole history. The two scanners' tests hold fake keys built by concatenation (`"AKIA" + "..."`), allowlisted by path in `.gitleaks.toml`. |
| No credential from the user's environment sent to a server | Pass | No hook or server reads one. `emulator-fidelity` exports the emulator's own per-run throwaway keys and sends them only to `127.0.0.1`. `javatopython-converter`'s workflow template uses `${{ secrets.GITHUB_TOKEN }}` inside the generated project's GitHub Actions, not on the user's machine. A reviewer may still read these. |
| `.mcp.json` valid | N/A | None. |
| Remote MCP servers use `https`/`wss` | N/A | None. |
| Local MCP servers start a plugin file with plain arguments | N/A | None. |
| Hook and MCP command paths written from `${CLAUDE_PLUGIN_ROOT}` | N/A | No hooks or MCP servers. |
| Scripts run by hooks or MCP servers have no launchers or substitutions | N/A | No hooks or MCP servers; the bundled scripts are run only when a `SKILL.md` tells Claude to, which this check excludes. |

### Choices a reviewer always checks

| Check | Result | Evidence |
|---|---|---|
| Package from a registry | N/A | None run by the plugin. |
| Lockfile install | N/A | No `package.json` or lockfile at the root. |
| Program the validator can't read (hooks, servers, `` !`…` `` lines) | N/A | No hooks, servers or `` !`…` `` lines in any skill. |

### Hooks, skills, commands and agents

| Check | Result | Evidence |
|---|---|---|
| `hooks/hooks.json` valid | N/A | No hooks. |
| `hooks/hooks.json` not named in `plugin.json` | N/A | No hooks. |
| Valid YAML front matter with a single-text `description` | Pass | `tools/validate_skills.py` checks every `SKILL.md` in CI (strict YAML, name equals folder, description at most 1024 characters). |
| Exact folder and file spelling (`SKILL.md`) | Pass | Every skill folder holds `SKILL.md`; skills are listed by path, so no `skills/` folder is needed. |

### Security scan and behaviour

| Check | Result | Evidence |
|---|---|---|
| README describes everything the plugin runs, sends or fetches | Pass | README section "Privacy and data handling". |
| Readable source, nothing compiled or minified | Pass | Markdown and plain Python. |
| Compare output with and without the plugin (`claude plugin eval`) | Open | Recommended, not a gate. No eval suite yet; the skills have been used on real PRs. |
| Load the plugin on each surface | Pass in Claude Code; open on claude.ai and Cowork | Local marketplace install works (above). Try one install on claude.ai after submitting, as [Surface compatibility](#surface-compatibility) explains. |

Counted: rows marked Pass 27; N/A 15; Open 2 (the name check and the eval). The surface row counts as Pass for Claude Code, with the claude.ai check listed under portal steps.

### Things the user asked to weigh

| Topic | Result |
|---|---|
| Privacy and data handling | README "Privacy and data handling"; `privacyPolicyUrl` points to it. The portal's data-handling answers are under [Portal steps](#portal-steps). |
| No secrets | Pass (gitleaks on PRs, pushes and weekly history; masked output everywhere). |
| Safe defaults | Report-only or ask-first for every public or irreversible action: `pr-triage` acts only with `--apply`; `emulator-fidelity` files public issues only after the user approves the first one, and a background run without that approval is `--report-only`; `secret-history-scan` checks liveness only with `--verify` and the user's yes, and sends a secret only to its own issuer; merges never use admin or force. |
| No network calls without consent | Network use is the user's own `gh` on their own repositories (the purpose of the PR skills), public docs and registry metadata, and the two consent-gated cases above. |
| Clear descriptions | Every skill description says what it does, when to use it, what it is not for, and its arguments (CI checks the `Args` part and the 1024-character limit). |
| Support contact | `supportUrl`: https://github.com/manojkhanwalkar/claude-skills/issues. `SECURITY.md` covers vulnerability reports. |
| Screenshots or examples | Not required by the directory; the README's skill table and examples cover it. |

## Surface compatibility

The plugin holds only skills, which load in chat, Cowork and Claude Code [platforms]. Loading is not the same as working: most skills drive `git`, `gh`, a shell, local files, subagents or Claude Code's built-in `/code-review` and `/security-review`.

| Skill | Needs | Claude Code | Cowork | claude.ai chat |
|---|---|---|---|---|
| pr-review, pr-walkthrough, fix-ci, resolve-conflicts, post-merge-sync, pr-triage | `gh`, `git`, a checkout, subagents | Yes | No | No |
| review-guidelines, port-parity, javatopython-converter, deep-review | `git`, `gh`, a checkout | Yes | No | No |
| secret-history-scan | Full git history, bundled script | Yes | No | No |
| emulator-fidelity | Runs the emulator locally, `gh issue create` | Yes | No | No |
| token-efficiency-review | Claude Code's local transcripts | Yes | No | No |
| owasp-top10, owasp-llm-top10, compliance-check, digital-regulation-check, ada-compatibility | Project files; bundled scanners need Python | Yes | Partly: report on a project folder, no PR steps | Partly: review pasted or uploaded code |
| design-patterns, perf-review, dynamodb-optimizer, resiliency, microservices-refactor | Project files | Yes | Partly | Partly |
| test-gen, documenter, document, mcp-builder | Project files, build tools | Yes | Partly | Partly: advice and drafts only |

**Verdict:** submit the whole plugin, not a separate Claude Code-only one. Every skill works in Claude Code, and none breaks anything elsewhere: on claude.ai and Cowork the review and audit skills can still report on code they are given, and the rest say what they need. A split would mean two listings and two names to keep in step. The description says so up front ("Built for Claude Code; most need git, gh and a shell"), and the README repeats it, so a reviewer or a chat user isn't surprised.

## Portal steps

1. **Before you start:** merge this PR. On claude.ai, in the organization you submit from, connect your GitHub account (the portal offers **Connect GitHub** when it is missing); it must be able to push to `manojkhanwalkar/claude-skills`. The repository is public, so no Claude GitHub App or source-upload consent is needed.
2. **Open** [claude.ai/directory/manage](https://claude.ai/directory/manage), select **Submit new**, then **Plugin bundle**.
3. **Source:** Repository `manojkhanwalkar/claude-skills`; Plugin path empty (the root); Branch or tag `master` (or leave empty, the default branch). Select **Validate**, and fix any **Blocking** finding in a PR, then **Re-validate**.
4. **Listing details:** check that it shows `Manoj Skills`, the current version (`1.1.0`), the description and the README; change them only through `plugin.json` or the README.
5. **Data handling:** reads or stores personal data: *Yes, reads* (your code, git history, CI logs and local Claude Code transcripts, on your machine, which may contain personal data; scanners mask what they find; it stores nothing of its own outside your files, repositories and project memory). Sends data to services other than declared connectors: *Yes*: to GitHub through your own `gh` (PRs, comments, merges, new repositories, and issues you approve), to claude.ai docs through your own connectors when your memory names a design doc, to a secret's issuer for a liveness check you approve, and reads from public docs, registries and `downloads.aws.com`; all listed in the README's privacy section. Retention: *none*; reports stay in local files you control. Intended for people under 18: *No*.
6. **Compliance:** confirm the contact email (the portal's field; the repository carries no email) and select all four acknowledgements.
7. **Review and submit:** keep **GitHub push webhook** (needs repository admin; select **Set up push updates** afterwards), leave **Auto-publish passing versions** off for the first version, then **Submit for review**.
8. **After review:** when the version passes, select **Publish**. Then install it once from **Customize > Plugins** on claude.ai to see how it loads there.

**Later releases:** merge to `master` with `version` raised (CI requires it when anything the plugin ships changes); the directory scans each new commit and publishes it under the plugin's publish setting. If a scan holds or fails a version, the plugin's **Versions** tab says why.
