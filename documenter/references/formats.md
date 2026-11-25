# Doc comment formats by language

Match the project's existing style first; these are the defaults when it has none. The rules for what to document (class comment always, methods over the threshold, public API where a reader needs it, exemptions) are the same in every language.

## Java (Javadoc)

```java
/**
 * Summary fragment, capitalised and ending with a period.
 *
 * <p>Further paragraphs start with {@code <p>} on the first line of the paragraph.
 * Code, names and literals go in {@code ...}; references to other types use
 * {@link Type#method(ArgType)} the first time only.
 *
 * @param name what it is, its unit, and what null or empty means
 * @return what comes back, including empty, null or Optional cases
 * @throws IllegalArgumentException when {@code limit} is below 1
 */
```

- **First sentence** is the summary: the javadoc tool copies it into indexes. Google style: a noun phrase or verb phrase, not a full sentence ("Returns the customer ID.", not "This method returns..."). Oracle: third person ("Gets", not "Get"); describe beyond the name.
- **Block tag order:** `@param`, `@return`, `@throws`, `@deprecated` (Google); `@see`, `@since` after them. No tag with an empty description. `@param` in parameter order, names matching exactly; type parameters as `@param <T>`.
- **`@throws`**: every checked exception, and the unchecked ones a caller can sensibly avoid or handle, each with its condition.
- **Records:** document components with `@param` on the record's comment; accessors need nothing more.
- **Overrides:** `{@inheritDoc}` or nothing, unless the behaviour differs from the supertype's contract.
- **Code examples:** `{@snippet : ... }` (JEP 413, Java 18+) instead of `<pre>{@code ...}</pre>` on Java 18+; keep examples short and compilable.
- **Markdown comments** (`///`, JEP 467, Java 23+): same tags, Markdown in place of HTML (`` `code` ``, `[Type#method()]` links, blank lines for paragraphs). Use them only when the project already does; never mix both styles in one file, never convert a project.
- **HTML:** escape `<`, `>` and `&` outside `{@code}`; doclint fails on malformed HTML and on self-closing `<p/>`.
- **Package docs:** `package-info.java` for a package's purpose, when the project has them.

## Kotlin (KDoc)

```kotlin
/**
 * Summary paragraph in Markdown.
 *
 * Use [OtherType] and [member] links, not {@link}.
 *
 * @param member what it is.
 * @return the new size of the group.
 * @throws IllegalStateException when the group is closed.
 * @property name on a class, for a primary-constructor property.
 * @constructor on a class, when the primary constructor needs a note.
 */
```

- Markdown, not HTML. `@property` for constructor properties. No `@deprecated` tag; the `@Deprecated` annotation carries it. Dokka renders it.

## Python (PEP 257 docstrings)

```python
def claim_due(table, now, limit=100):
    """Claim unsent alerts older than the lookback and return them.

    Each returned alert is marked claimed in the same conditional write, so two
    runs never send the same alert.

    Args:
        table: the DynamoDB table resource.
        now: the run's clock reading, timezone-aware.
        limit: most alerts to claim; the rest wait for the next run.

    Returns:
        The claimed alerts, oldest first; empty when none are due.

    Raises:
        ClientError: when DynamoDB refuses the write after retries.
    """
```

- Triple double quotes. One-liners fit on one line with the quotes. Multi-line: a summary line, a blank line, then the rest; closing quotes on their own line.
- PEP 257: the summary is an imperative phrase ending in a period ("Return ...", not "Returns ..."), and doesn't repeat the signature.
- Sections: follow the project (Google style `Args:` / `Returns:` / `Raises:`, NumPy style, or reST `:param x:`). Default to Google style.
- Class docstring: what the class is for, its public behaviour and attributes; the constructor's arguments go in `__init__`'s docstring or the class one, as the project does. Module docstring at the top of the file.
- Type hints carry the types; don't repeat them in the text.
- Docstrings are runtime values: `>>>` examples run under doctest, and click, typer and `argparse(description=__doc__)` print them as CLI help. Grep for `doctest` and `__doc__` first; keep such examples passing and such help text meaningful.

## TypeScript (TSDoc) and JavaScript (JSDoc)

```ts
/**
 * Fetches the user's latest credit report, using the cache when it is fresh.
 *
 * @remarks
 * Longer notes go under remarks.
 *
 * @param userId - The signed-in user's ID.
 * @param maxAgeMs - Oldest cached report to accept, in milliseconds.
 * @returns The report, or `undefined` when the user has none.
 * @throws {@link ReportUnavailableError} When the bureau call times out.
 */
```

- TSDoc: `@param name - description` (hyphen), `@returns`, `@throws`, `@remarks`, `@example`, `{@link}`; no types in tags (TypeScript has them).
- JSDoc (plain JavaScript): types in braces, which tools such as `tsc --checkJs` read: `@param {string} userId The signed-in user's ID.`, `@returns {Promise<Report|undefined>}`.
- Class and module comments on the class and at the top of the file (`@packageDocumentation` in TSDoc, `@module` or `@file` in JSDoc).

## Go (doc comments)

```go
// AlertMailer sends alert emails for new credit alerts, at most once per alert.
// It is safe for concurrent use.
type AlertMailer struct { ... }

// SendDue claims the alerts due at now and emails each subscriber once.
// It returns the number sent and the first error that stopped the run.
func (m *AlertMailer) SendDue(ctx context.Context, now time.Time) (int, error)
```

- `//` line comments directly above the declaration, no blank line between. The first sentence is a full sentence that **begins with the declared name**. Every exported name gets one.
- Package comment (`// Package alerts ...`) before the `package` clause, in one file only (often `doc.go`).
- No tags: parameters, results and errors are described in sentences. `[Name]` links to other identifiers (Go 1.19+). `gofmt` reformats doc comments: check with `gofmt -d <file>` and apply only its changes to your comments, since on a file that wasn't gofmt-clean it reformats code too.
- Directives (`//go:build`, `//go:embed`, `//go:generate`, `//export`) and the cgo preamble (the comment directly above `import "C"`, which is C code) are not doc comments: never edit them.

## Other languages

Use the language's standard: Rust `///` and `//!` with `# Errors` and `# Panics` sections; C# XML docs (`/// <summary>`, `<param>`, `<returns>`, `<exception>`); Swift `///` with `- Parameter` and `- Returns`. Same rules on what to document and what to skip.
