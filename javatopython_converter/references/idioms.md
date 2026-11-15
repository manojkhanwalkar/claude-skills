# Java → Python mapping

Pick versions from PyPI at conversion time (`uv add <pkg>` resolves the newest), never from memory.

## Frameworks (defaults)

| Java | Python default | Notes |
|---|---|---|
| Spring Boot web (`@RestController`) | **FastAPI** + **uvicorn** | Pydantic models for request/response; `Depends` for injection; exception handlers mirror `@ControllerAdvice` status mapping. |
| Spring WebFlux / reactive | FastAPI with `async def` | |
| Spring AI MCP server (`@McpTool`) | official **`mcp`** SDK. For byte-for-byte parity use the low-level `mcp.server.lowlevel.Server` (`on_list_tools` / `on_call_tool`); the high-level `MCPServer` (`mcp.server.mcpserver`; it was `FastMCP` in `mcp` 1.x) adds titles and output schemas, advertises prompts/resources, hides exception messages and turns unknown tools into tool results | Keep tool names, descriptions, annotations, input schemas, capabilities and error texts identical — capture them from the Java server (see SKILL.md *Golden tests*); stdio by default, `streamable-http` if Java used HTTP. |
| Spring AI MCP client | `mcp` SDK `ClientSession` + `mcp.client.stdio.stdio_client` / `mcp.client.streamable_http.streamable_http_client` | Pass a `read_timeout_seconds` (Spring AI's default request timeout is 20 s). `list_tools()` returns one page — follow `next_cursor` (with a page cap) as Java does. Servers it starts get only a minimal environment (HOME, PATH, …), unlike Java's `ProcessBuilder`; document it. On end of input a stdio server cancels requests still in flight, so a client (or test harness) must wait for every reply before closing stdin. |
| Spring AI `ChatClient` / LangChain4j | **`anthropic`** SDK (or the provider the Java code used) | Keep model ids and prompts; load the `claude-api` skill before writing model calls. |
| Spring `@Configuration` / `application.yml` | **pydantic-settings** `BaseSettings` | `a.b.c` property → `A_B_C` env var; keep the same defaults. |
| Spring DI (`@Component`, `@Autowired`) | plain constructors + a small composition root (`app.py`) | No DI framework unless the graph is large. |
| Spring Data JPA / JDBC | **SQLAlchemy 2.x** (+ Alembic) | |
| Spring `@Scheduled` | `asyncio` task loop, or APScheduler if cron expressions are used | |
| Spring Security / JWT | FastAPI security deps + **PyJWT** | Same algorithms, issuer/audience checks, clock skew. |
| picocli / commons-cli / `main(String[])` | **argparse** (stdlib); **typer** if subcommands are many | Same flags and exit codes. |
| Servlet filters | Starlette middleware | |

## Libraries

| Java | Python |
|---|---|
| JUnit 5 / TestNG | **pytest** (`@ParameterizedTest` → `@pytest.mark.parametrize`, `@BeforeEach` → fixtures) |
| Mockito | `unittest.mock` / `pytest-mock` |
| AssertJ / Hamcrest | plain `assert`, `pytest.approx`, `pytest.raises(match=...)` |
| WireMock / MockWebServer | **respx** (httpx) or `pytest-httpserver` |
| Testcontainers | `testcontainers` (Python) |
| Spring `MockMvc` / `WebTestClient` | FastAPI `TestClient` / `httpx.AsyncClient(transport=ASGITransport(app))` |
| JaCoCo | **coverage.py** via pytest-cov |
| Jackson | **Pydantic v2** (`model_validate_json`, `model_dump(by_alias=True)`); `json` for simple cases |
| Lombok `@Data` / records | `@dataclass(frozen=True, slots=True)` or Pydantic `BaseModel` |
| `java.net.http.HttpClient` / RestTemplate / WebClient / OkHttp | **httpx** (explicit `timeout=` always) |
| Resilience4j / Spring Retry | **tenacity** (retry only recoverable + idempotent; `wait_random_exponential`) |
| Bucket4j / Guava RateLimiter | small token-bucket class + `asyncio.Semaphore` for the concurrency cap |
| Caffeine / Guava cache | `functools.lru_cache(maxsize=…)` or `cachetools.TTLCache` — always bounded |
| SLF4J / Logback | `logging` (`logging.getLogger(__name__)`), config via `logging.config.dictConfig` |
| Guava collections | stdlib `collections`, `itertools` |
| Apache Commons Lang/IO | stdlib (`str` methods, `pathlib`, `shutil`) |
| `java.time` | `datetime` (always timezone-aware), `zoneinfo` |
| `BigDecimal` | `decimal.Decimal` with an explicit context/rounding |
| `ExecutorService` / `CompletableFuture` | `asyncio` (I/O) or `concurrent.futures` (CPU) |
| `AtomicInteger` / `synchronized` | `threading.Lock` (threads) / `asyncio.Lock` (async) — or avoid shared state |
| `Optional<T>` | `T | None` |
| Checked exceptions | a package exception hierarchy rooted at `<Pkg>Error` |
| Jakarta Validation (`@NotNull`, `@Size`) | Pydantic `Field(...)` constraints |

## Semantics that bite

- **Integer overflow:** Java `int`/`long` wrap; Python ints don't. If results can overflow and the contract depends on it, mask explicitly (`((x + 2**31) % 2**32) - 2**31`) and test it.
- **Integer division:** Java `int / int` truncates toward zero; Python `//` floors. Use exact integer arithmetic — `q = abs(a) // abs(b); q = q if (a < 0) == (b < 0) else -q` (or `math.trunc(Fraction(a, b))`). Never `int(a / b)`: it goes through a float and is wrong for `long`-sized values. Test negatives.
- **Integer remainder** of negatives differs (`-7 % 3` is `-1` in Java, `2` in Python): `a - b * q` with the truncated `q` above. For `double`, Java `%` is `math.fmod`.
- **Double formatting:** Java prints `1.0E10`, `NaN`, `Infinity`; Python prints `10000000000.0`, `nan`, `inf`. Reproduce `Double.toString` where it is part of the output contract: shortest round-trip digits (same as Python `repr`), but at least two significant digits — when the shortest has one, Java prints the closest two-digit decimal (`5e-324` → `4.9E-324`, `1e21` → `1.0E21`) — plain notation for `1e-3 <= |x| < 1e7`, otherwise `d.dddE±n`.
- **`Math.rint` keeps the sign** (`rint(-0.3)` is `-0.0`); Python `round()` returns an `int` and loses it. Use `math.copysign(float(round(x)), x)`.
- **`Math.pow`/`log`/`exp`** are only specified to within 1 ulp, and Java's `Math.pow` and `StrictMath.pow` already disagree on some inputs; Python's `math.pow` (C libm) can differ from Java by 1 ulp. Compare those results with a 1-ulp tolerance and say so in the design doc; compare everything else exactly. `math.pow` also raises `OverflowError`/`ValueError` where Java returns `Infinity`/`NaN` — map them.
- **Integer powers:** C's `pow` and Java's `Math.pow` round a result that lies halfway between two doubles differently (`9^17`). For a whole base and a whole exponent `0..64` whose exact value is cheap, compute `base**exp` exactly and convert once (`float(int)` rounds half-even): that removes the systematic halfway difference and matched Java for small bases, but Java's `Math.pow` isn't correctly rounded either (e.g. `99^49`, `103^8` differ), so keep a 1-ulp tolerance for power results and check against seeded random Java captures. For negative exponents use `math.pow` (it matched Java better than an exact `Fraction`), within 1 ulp.
- **`Math.log10` (and on some CPUs/JDKs `Math.log`) can differ from libm by an ulp** on non-round inputs; results built from them (`log(x)/log(b)`) can differ further. Round-number golden sets hide this — capture a few hundred seeded random inputs too, measure, and set each affected tool's ulp limit from the data (errors and every other tool compared exactly).
- **Jackson writes non-finite doubles as JSON strings** (`"NaN"`, `"Infinity"`, `"-Infinity"`): in a Java tool's result text *and* in a Java client's request arguments (where the server then reports a type error). Reproduce both.
- **`Double.parseDouble` ≠ `float()`:** Java trims only characters `<= U+0020`, accepts `1d`/`2.5f` suffixes, hex floats (`0x1p3`, exponent required: `0x1.0` is rejected) and signed `NaN`/`Infinity` (no suffix: `NaNd` is rejected), and rejects `1_000`, `1L` and Unicode whitespace; a hex float that overflows is `Infinity` (Python's `float.fromhex` raises `OverflowError`). Port the grammar with a regex and check it against a jshell-generated fixture.
- **`String.lines()` splits only on `\n`, `\r`, `\r\n`;** Python's `splitlines()` also splits on `\v`, `\f`, `\x1c-\x1e`, `\x85`, `\u2028`, `\u2029`. All lines: `parts = re.split(r"\r\n|\r|\n", text)`, then drop a final `""` (so `""` gives `[]` and `"a\n"` gives `["a"]`, as in Java). First line (`lines().findFirst().orElse("")`): `re.split(r"\r\n|\r|\n", text, maxsplit=1)[0]`.
- **Spring Boot command lines:** `--name=value` options may appear anywhere; a bare `--` ends option parsing and is dropped (everything after it is positional, even `--x=y`); `--=x` is a start-up error. Relaxed binding also maps environment variables (`CALCULATOR_SERVER_JAR` → `calculator.server.jar`).
- **Division by zero:** Java `double` gives `Infinity`/`NaN`; Python raises `ZeroDivisionError`. Match the Java result or the Java error contract deliberately.
- **String:** Java `String.length()` counts UTF-16 units; Python `len()` counts code points. `split` with regex vs literal; Java `trim()` vs Python `strip()` (different whitespace sets).
- **Equality:** `==` on Java objects is identity; Python `==` is value equality. `equals`/`hashCode` → dataclass `eq`/`frozen`.
- **Collections ordering:** `HashMap` order is unspecified; Python `dict` keeps insertion order. Don't make tests depend on one or the other unless the contract does.
- **Null handling:** a Java method that returns `null` → return `None` and type it `T | None`; don't silently change to raising.
- **Static mutable state / singletons:** module-level state is shared per process; make it explicit and bounded.

## Idiom checklist (reviewers look for these Java-isms)

- getters/setters → attributes or `@property`
- classes with only static methods → module-level functions
- `try/finally: close()` → `with`
- `if x == None` → `if x is None`
- `for i in range(len(xs))` → `for x in xs` / `enumerate`
- string concatenation in loops → `"".join(...)` / f-strings
- `interface` with one impl → drop it, or a `typing.Protocol`
- builders → keyword arguments with defaults
- `CamelCase` methods/variables → `snake_case`; constants `UPPER_SNAKE`
- explicit type checks (`instanceof` chains) → `match` statement or polymorphism
