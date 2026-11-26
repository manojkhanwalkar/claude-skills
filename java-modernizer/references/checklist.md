# Modernization checklist

Each row: the old idiom, a grep to find it, the replacement and the release it needs, and the pitfall that makes a swap wrong. Confirm every hit by reading the code.

## Removed or deprecated APIs

| Old | Grep | Replacement (JDK) | Pitfall |
|---|---|---|---|
| Boxed constructors | `new (Integer\|Long\|Double\|Boolean\|Short\|Byte\|Character\|Float)\(` | `valueOf` or autoboxing (5) | Identity: code comparing boxes with `==` changes behaviour for cached values; fix the `==` too |
| `finalize()` | `void finalize\(` | try-with-resources, `Cleaner` (9) | Callers that never closed the resource now must; add `AutoCloseable` |
| `Thread.stop/suspend/resume` | `\.stop\(\)\|\.suspend\(\)` on threads | Interrupt plus a checked flag | Code must check `isInterrupted` |
| `new URL(` | `new URL\(` | `URI.create(…).toURL()` (20) | `URI` is stricter about illegal characters: encode first |
| `URL` in `equals`, `hashCode`, sets or map keys | `Set<URL>`, `Map<URL` | `URI` | `URL.equals` does DNS lookups and blocks |
| `new Locale(` | `new Locale\(` | `Locale.of` (19) | none |
| `Thread.getId()` | `\.getId\(\)` on threads | `threadId()` (19) | none |
| Security Manager | `SecurityManager\|AccessController\|doPrivileged` | Remove (24) | Check what policy it enforced and say where that control moves |
| `sun.misc.*`, `com.sun.*` internals | `import sun\.\|import com\.sun\.` (not `com.sun.net.httpserver`) | Public API (`VarHandle`, `Base64`, `HexFormat`) | `jdeps --jdk-internals` lists them |
| Reflection writing `final` fields | `setAccessible(true)` plus `Field.set` | Constructor or builder | Frameworks (Jackson, Hibernate) need their own upgrade, not a code change |

## Bug-prone idioms

| Old | Grep | Replacement (JDK) | Pitfall |
|---|---|---|---|
| Manual `close()` in `finally` | `finally\s*\{` then `\.close\(\)` | try-with-resources (7) | Suppressed exceptions now attach to the primary one; check tests that assert the thrown exception |
| `SimpleDateFormat`, `Date`, `Calendar` arithmetic | `SimpleDateFormat\|Calendar\.getInstance\|new Date\(` | `DateTimeFormatter`, `Instant`, `LocalDate`, `ZonedDateTime` (8) | Wire and DB formats must not change: pin the exact output; `java.sql.Timestamp` conversions; time zones (use an explicit `ZoneId`, never the system default for business dates) |
| `Random` shared for security, `Math.random` for tokens | `new Random\(\|Math\.random` near tokens or ids | `SecureRandom` | A security finding: report it to the security area, don't treat it as modernization |
| Fall-through `switch` | `case .*:` without `break` | Switch expression (14) | Intentional fall-through: group the labels (`case A, B ->`) |
| Strings compared with `==` | `== "\|" ==` | `equals`, `Objects.equals` (7) | none |
| Charset left to the platform | `getBytes\(\)\|new String\(bytes\)\|new FileReader\(\|new InputStreamReader\([^,]*\)$` | Explicit `StandardCharsets.UTF_8` (7), `Files.newBufferedReader` | On 18+ the default is UTF-8; pre-18 deployments on other locales changed behaviour |
| `HashMap`/`ArrayList` exposed after `Collections.unmodifiable*` wrap of a live collection | `Collections\.unmodifiable` | `List.copyOf` (10) | `copyOf` rejects `null` elements |
| `Optional.get()` after `isPresent()` | `isPresent\(\)` | `map`, `orElse`, `ifPresentOrElse` (9), `orElseThrow()` (10) | none |
| `Optional` as a field or parameter | `Optional<.*> [a-z]+;` in fields | Nullable field with a getter returning `Optional` | Serialization frameworks |

## Boilerplate

| Old | Grep | Replacement (JDK) | Pitfall |
|---|---|---|---|
| Immutable data class (final fields, constructor, getters, `equals`, `hashCode`, `toString`), Lombok `@Value` | `@Value\|@Data` with all-final fields | `record` (16) | Accessor names change (`getX` to `x`): internal types only, or check every caller, JSP/EL, templates, Jackson and MapStruct; JPA entities can't be records; records can't extend a class |
| `instanceof` then cast | `instanceof \w+\)` followed by a cast | Pattern `instanceof` (16) | none |
| `if`/`else if` chains on type, enum switch statements assigning one variable | `instanceof` chains; `switch` with assignments | Pattern `switch`, record patterns (21) over a sealed hierarchy (17) | Exhaustiveness: a `default` hides new subtypes; with sealed types drop it |
| Multi-line strings by concatenation (SQL, JSON, HTML) | `"\\n" \+` | Text block (15), `formatted` | Trailing spaces and the final newline differ: pin the exact string in a test |
| Anonymous class implementing a functional interface | `new (Runnable\|Callable\|Comparator\|Function\|Supplier)<` | Lambda or method reference (8) | `this` means the enclosing instance in a lambda |
| `Comparator` by hand | `compare\(.*\) \{` | `Comparator.comparing(…).thenComparing(…)` (8) | Null handling: `nullsFirst` |
| Get, check null, put | `get\(.*\);\s*if \(.* == null\)` | `computeIfAbsent`, `merge`, `getOrDefault` (8) | On `ConcurrentHashMap`, `computeIfAbsent` holds a bin lock: keep the function short and side-effect free |
| `Arrays.asList` / `Collections.unmodifiableList(Arrays.asList(…))` for constants | `Arrays\.asList\(` | `List.of` (9) | `null` elements; `List.of` is immutable, `Arrays.asList` allows `set` |
| `list.get(0)`, `list.get(list.size() - 1)`, `descendingIterator` | `get\(0\)\|size\(\) - 1\)` | `getFirst`, `getLast`, `reversed` (21) | Empty list throws `NoSuchElementException` instead of `IndexOutOfBoundsException` |
| `collect(Collectors.toList())` | `Collectors\.toList\(\)` | `toList()` (16) | Result is unmodifiable: check callers that add or sort it |
| Unused catch or lambda parameters named `ignored`, `e` | `catch \(\w+ ignored\)` | `_` (22) | none |
| Reading a whole file by hand | `BufferedReader` loops into a `StringBuilder` | `Files.readString`, `Files.readAllLines` (11) | Unbounded memory for big files: keep streaming there |
| `String.trim()` for Unicode input, `length() == 0` | `trim\(\)\.isEmpty\|\.length\(\) == 0` | `strip`, `isBlank` (11), `isEmpty` (6) | `strip` removes Unicode whitespace that `trim` kept |
| `Math.max(lo, Math.min(hi, x))` | `Math\.max\(.*Math\.min` | `Math.clamp` (21) | Throws when `lo > hi` |
| `ThreadLocal` for request context | `ThreadLocal<` | Scoped value (25) | Only where the value is bound once per scope and read below it; mutable thread-locals stay |
| Constructor validation after `super(...)` through a static helper | `super\(validate` | Statements before `super(…)` (25) | Can't touch `this` before the call |

## Platform features

| Old | Replacement (JDK) | Rule |
|---|---|---|
| `HttpURLConnection`, Apache HttpClient 4 for simple calls | `java.net.http.HttpClient` (11) | Keep the existing client if the project standardised on it; timeouts per the `resiliency` checklist |
| Fixed thread pools sized for blocking I/O | `Executors.newVirtualThreadPerTaskExecutor()` (21) | Hand to `concurrency-audit`'s rules: no pooling of virtual threads, a semaphore where a downstream limit existed, `synchronized` pinning before 24 |
| `Thread` subclasses | `Thread.ofVirtual()` / `ofPlatform()` builders (21) or an executor | none |
| `Executors.newFixedThreadPool` never shut down | try-with-resources on `ExecutorService` (19, it is `AutoCloseable`) | `close()` waits for tasks |
