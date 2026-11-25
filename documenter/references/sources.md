# Sources

Checked on 2026-11-25 when this skill was written. Two sites (oracle.com and openjdk.org) refuse automated fetches; for those, the pages are cited from their public text and confirmed by search results.

- [Oracle, How to Write Doc Comments for the Javadoc Tool](https://www.oracle.com/technical-resources/articles/java/javadoc-tool.html): the first sentence as a summary, third-person descriptions that say more than the name, `<code>` (now `{@code}`) for keywords and names, tag order, and when to document `@throws`.
- [Google Java Style Guide, section 7 Javadoc](https://google.github.io/styleguide/javaguide.html#s7-javadoc): the summary fragment (a noun or verb phrase), where Javadoc is required (visible classes and members, record components), the exemptions for simple obvious members and overrides, and the tag order `@param`, `@return`, `@throws`, `@deprecated` with no empty descriptions; both `///` and `/** */` accepted.
- [JEP 413, Code Snippets in Java API Documentation](https://openjdk.org/jeps/413): the `{@snippet}` tag (Java 18) for examples, replacing `<pre>{@code}</pre>`.
- [JEP 467, Markdown Documentation Comments](https://openjdk.org/jeps/467): `///` comments written in Markdown, delivered in JDK 23; standard tags still work. Also [Oracle, Markdown in Documentation Comments (JDK 24)](https://docs.oracle.com/en/java/javase/24/javadoc/using-markdown-documentation-comments.html).
- [PEP 257, Docstring Conventions](https://peps.python.org/pep-0257/): one-line and multi-line docstrings, the imperative summary ending in a period, the blank line after the summary, class and module docstrings.
- [TSDoc](https://tsdoc.org/): the TypeScript doc comment standard, loosely based on JSDoc; `@param name - description`, `@returns`, `@remarks`, `@throws`.
- [JSDoc, Getting started and block tags](https://jsdoc.app/): JSDoc tags with types in braces for plain JavaScript.
- [Kotlin, Document Kotlin code: KDoc](https://kotlinlang.org/docs/kotlin-doc.html): KDoc syntax, Markdown markup, `[name]` links, `@param`, `@return`, `@throws`, `@property`, `@constructor`, and no `@deprecated` tag.
- [Go, Go Doc Comments](https://go.dev/doc/comment): comments directly above declarations, the first sentence beginning with the declared name, package comments in one file, `[Name]` links.
