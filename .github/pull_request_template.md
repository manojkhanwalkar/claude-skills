## What and why

<!-- One or two sentences. -->

## Checklist

- [ ] `python3 tools/validate_skills.py .` passes (frontmatter is strict YAML, name equals the folder, description ≤ 1024 characters with no `<`/`>`, links resolve, README row present)
- [ ] Scripts changed: their tests updated, and `tools/run_tests.sh` passes the 95% coverage gate
- [ ] The README table describes the skill as it now is
- [ ] Reviewed by a separate agent (`pr-review`); findings table posted
- [ ] No secrets, personal data or machine-specific paths (use `~/...` and placeholders)
