# Sources

- Brian Goetz et al., *Java Concurrency in Practice* (thread safety, publication, check-then-act, lock ordering, executors, cancellation).
- Joshua Bloch, *Effective Java*, 3rd edition, chapter 11 (Concurrency).
- Java Language Specification, chapter 17 (Threads and Locks, the memory model).
- JEP 444 (Virtual Threads), JEP 491 (Synchronize Virtual Threads without Pinning, JDK 24; removes `jdk.tracePinnedThreads`), JEP 506 (Scoped Values, final in JDK 25), JEP 505 and JEP 525 (Structured Concurrency, fifth and sixth previews in JDK 25 and 26): https://openjdk.org/jeps/
- JDK 25 release notes (scoped values final, structured concurrency preview): https://www.oracle.com/java/technologies/javase/25-relnote-issues.html
- InfoQ, "Java 26 released" (structured concurrency still a preview): https://infoq.com/news/2026/03/java26-released
- Roman Leventov, "Code review checklist: Java concurrency": https://www.freecodecamp.org/news/code-review-checklist-java-concurrency-49398c326154/
- Hovemeyer and Pugh, "Finding Concurrency Bugs in Java" (pattern-based detection, the basis of FindBugs and SpotBugs): https://www.cs.jhu.edu/~daveho/pubs/csjp2004.pdf
- SpotBugs bug descriptions (multithreaded correctness category): https://spotbugs.readthedocs.io/en/latest/bugDescriptions.html
- Sonar Java multi-threading rules, including virtual-thread rules (RSPEC-6881): https://rules.sonarsource.com/java/tag/multi-threading/RSPEC-6881
- OpenJDK jcstress: https://github.com/openjdk/jcstress
- Go race detector: https://go.dev/doc/articles/race_detector ; Python `asyncio` development mode: https://docs.python.org/3/library/asyncio-dev.html ; Kotlin coroutines guide: https://kotlinlang.org/docs/coroutines-guide.html
