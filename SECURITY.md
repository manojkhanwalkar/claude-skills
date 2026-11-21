# Security policy

## Reporting a vulnerability

Please do **not** open a public issue. Use GitHub's private vulnerability reporting
(*Security → Report a vulnerability* on this repository).

## Scope

These are Claude Code skills: instructions plus a few small, standard-library Python scanners
(`*/scripts/`). Relevant reports include a scanner that executes or imports untrusted content,
prints a secret it should mask, or writes outside the paths it is given, and skill instructions
that would lead an agent to leak data, run untrusted code, or act without the user's approval.

The scanners' test fixtures contain fake keys and numbers made to look real on purpose; they are
not leaked secrets.
