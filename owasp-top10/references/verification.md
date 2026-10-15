# Verifying security fixes

Passing unit tests can give false confidence. An incremental build can leave a deleted secret in the output directory, so the "fixed" artifact still ships it while every test passes. Go as high on this ladder as is safe and practical, and record in the report which level each fix reached.

1. **Build and existing tests pass.** Record the baseline before the first edit.
2. **Regression test.** A test that would fail without the fix and passes with it.
3. **Artifact inspection, always from a clean build:** `mvn clean package`, `gradle clean build`, `rm -rf dist && npm run build`, `docker build --no-cache`. Incremental builds keep deleted files in output directories. Then list the contents (`unzip -l *.jar`, `tar tzf`, `docker run --rm <img> ls`, `npm pack --dry-run`) and grep for the removed secret, file or dependency.
4. **Live probe.** Start the service locally with a dev config and throwaway generated credentials, then probe the specific fix:
   - **Bind address:** `ss -ltnp` or `lsof -iTCP -sTCP:LISTEN`.
   - **Authorization and validation:** `curl` with a bad or missing token, a wrong key type, or an oversized body. Expect a 4xx, not a 5xx.
   - **Log injection:** send CR/LF in an input that gets logged, then check the log.
   - **Fail-closed configuration:** start without a required env var or secret. Expect a clean refusal to start, not a fallback default.
   - **Headers and cookies:** `curl -sI`.

   Stop every process you started. Never probe anything except localhost or targets the user named.
5. **End to end.** Run the project's own client, demo or smoke test to confirm legitimate use still works.

When a level isn't practical (no runnable entry point, external dependencies you can't start), say so in the Verification notes rather than implying the fix was proven.
