# Measurement

Measure before optimising, and again after. A figure in a finding is either measured (say how) or an estimate (say from what).

## Methodology

- **USE** (Brendan Gregg), per resource (CPU, memory, disk, network, pools, locks): utilisation, saturation (queued work), errors. Averages hide bursts: a CPU averaging 80% can be at 100% for seconds at a time. Above about 70% utilisation, queueing begins to hurt.
- **RED** (Tom Wilkie), per service or endpoint: request rate, errors, duration. Use with USE: RED says which endpoint is slow, USE says which resource is why.
- **CPU profile method**: take a CPU flame graph and understand everything over 1% of it. In a flame graph the width is the share of samples; the x-axis is not time.
- **Percentiles, not means**: report p50, p95, p99 (and p99.9 at scale). The mean hides the tail users feel.
- **Tail at scale** (Dean and Barroso): a request that fans out waits for the slowest leaf; with 100 leaves each slow 1 time in 100, 63% of requests are slow. Hedged requests send a second copy to another replica after a short delay; waiting for the 95th-percentile latency first limits the extra load to about 5%, and in their BigTable benchmark a hedge after 10 ms cut the 99.9th percentile from 1,800 ms to 74 ms for 2% more requests. Only for idempotent reads with replicas.
- **Little's Law**: items in a system = arrival rate × time in system (L = λW). 200 requests/s × 0.05 s = 10 requests in flight, so about 10 connections or threads busy on average; size pools above that for bursts. It holds over long-run averages, not short windows.
- **Amdahl's Law**: speedup = 1 / ((1 − p) + p/s). Speeding up 10% of the time 10,000× gives about 1.11× overall. Check what share of the request a fix can remove before spending effort.
- **Knuth**: forget small efficiencies about 97% of the time, but don't pass up the critical 3% — and find that 3% by measuring, not guessing.

## JMH (Java microbenchmarks)

For CPU and allocation claims about a piece of Java code. Use the archetype or a `jmh` source set (Gradle `me.champeau.jmh`); adding `jmh-core` alone isn't enough, and running from the IDE gives unreliable numbers.

```java
@State(Scope.Benchmark)
@BenchmarkMode(Mode.AverageTime) @OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 5, time = 1) @Measurement(iterations = 5, time = 1) @Fork(2)
public class MapperBench {
    private Report report;            // non-final field: avoids constant folding
    private final ObjectMapper shared = new ObjectMapper();
    @Setup public void setup() { report = Fixtures.report(); }

    @Benchmark public String perCall() throws Exception { return new ObjectMapper().writeValueAsString(report); }
    @Benchmark public String sharedMapper() throws Exception { return shared.writeValueAsString(report); }
}
```

Run: `java -jar target/benchmarks.jar MapperBench -prof gc` (`-prof gc` adds allocation per operation).

Pitfalls:

- **Dead code**: return the result or pass it to a `Blackhole`; a discarded result lets the JIT delete the work.
- **Constant folding**: read inputs from non-final `@State` fields, not literals or `final` fields.
- **Warm-up and forks**: keep warm-up iterations and at least 2 forks; profile-guided JIT differs between runs.
- **Loops inside the benchmark** get unrolled and hoisted; let JMH do the iterations.
- **Realistic data**: sizes and shapes from production, not 3-element lists.
- Benchmarks should be reviewed; a surprising result is more often a bad benchmark than a discovery.
- Keep JMH out of the normal test run; commit benchmarks under `src/jmh` when they guard a hot path, and put the before and after numbers in the commit message.

## Timing and call-count tests

For N+1 and chattiness, count, don't time: a spy or interceptor counts repository, client or SQL calls and the test asserts the batched number (`verify(client, times(1)).batchGetItem(any())`). This is deterministic and goes in the normal suite.

A timing test, when needed, uses a generous bound (several times the expected value) and fakes for remote calls with a fixed delay, so it proves "parallel, not sequential" (three 200 ms fakes finish in well under 600 ms) without being flaky.

## JFR and JMC

- Start with the app: `java -XX:StartFlightRecording=duration=60s,filename=rec.jfr,settings=profile -jar app.jar`.
- On a running JVM: `jcmd <pid> JFR.start duration=60s filename=rec.jfr settings=profile`; `JFR.dump`, `JFR.stop`.
- `default.jfc` is low overhead (production-safe); `profile.jfc` gives more detail at more cost.
- Read with JDK Mission Control or `jfr print --events jdk.ExecutionSample,jdk.ObjectAllocationSample,jdk.JavaMonitorEnter,jdk.VirtualThreadPinned rec.jfr`, or `jfr summary`.

## async-profiler

- `asprof -d 30 -f cpu.html <pid>` (CPU flame graph), `-e alloc` (allocations), `-e lock` (contention), `-e wall` (wall clock, including waiting threads: right for I/O-bound services).
- No safepoint bias, so it shows where time really goes; it also sees GC, JIT and native frames.

## Heap dumps and memory

- `jcmd <pid> GC.heap_dump /tmp/heap.hprof`, or `-XX:+HeapDumpOnOutOfMemoryError`. Open in Eclipse MAT: the dominator tree and leak suspects show what retains memory. Heap dumps contain personal data: keep them local, never commit or upload them, delete them after.
- `jcmd <pid> GC.class_histogram` for a quick count by class; compare two over time for growth.
- Native memory: `-XX:NativeMemoryTracking=summary` and `jcmd <pid> VM.native_memory summary` (adds overhead; diagnose only).

## Load tests

For latency and throughput claims at the service level. Run against a local or dedicated environment, never shared or production systems without the user's approval.

- **Open model**: use an arrival-rate executor (k6 `constant-arrival-rate` or `ramping-arrival-rate`; Gatling's open injection), so a slow server doesn't slow the load generator. A closed model (fixed virtual users looping) hides latency: when the server slows, fewer requests arrive (coordinated omission).

```javascript
// k6: 50 requests/s for 2 minutes against a local service
import http from 'k6/http';
export const options = {
  scenarios: { steady: { executor: 'constant-arrival-rate', rate: 50, timeUnit: '1s',
                         duration: '2m', preAllocatedVUs: 50, maxVUs: 200 } },
  thresholds: { http_req_duration: ['p(95)<300', 'p(99)<800'], http_req_failed: ['rate<0.01'] },
};
export default function () { http.get('http://localhost:8080/api/health'); }
```

- Report p50, p95, p99 and the error rate at a stated rate, before and after, on the same machine. Warm the JVM before measuring.
- Gatling suits JVM teams (simulations in Java or Kotlin); the same open-model and percentile rules apply.

## Python and Node

- Python: `python -m cProfile -s cumulative app.py` or `profiling.tracing` on 3.15+; `py-spy record -o profile.svg --pid <pid>` samples a running process with little overhead; `pytest-benchmark` for microbenchmarks.
- Node: `node --cpu-prof app.js` (a `.cpuprofile` for DevTools), or `node --prof` then `node --prof-process`; `autocannon` or k6 for load. Event-loop delay (`perf_hooks.monitorEventLoopDelay`) shows blocking. Clinic.js is unmaintained; use its results with care.
