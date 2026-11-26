# Examples

## Problem details (RFC 9457)

```http
HTTP/1.1 422 Unprocessable Content
Content-Type: application/problem+json

{
  "type": "https://api.example.com/problems/validation",
  "title": "Request validation failed",
  "status": 422,
  "detail": "2 fields are invalid",
  "instance": "/orders",
  "errors": [
    { "pointer": "/quantity", "detail": "must be greater than 0" },
    { "pointer": "/currency", "detail": "must be an ISO 4217 code" }
  ]
}
```

Spring Boot 3 / Spring 6:

```java
@RestControllerAdvice
class ApiErrors extends ResponseEntityExceptionHandler {   // handles framework exceptions (400, 405, 415) as ProblemDetail

    @ExceptionHandler(OrderNotFoundException.class)
    ProblemDetail notFound(OrderNotFoundException e) {
        ProblemDetail p = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, "Order not found");
        p.setType(URI.create("https://api.example.com/problems/not-found"));
        return p;
    }
}
```

Set `spring.mvc.problemdetails.enabled=true` (or extend `ResponseEntityExceptionHandler` as above) and `server.error.include-stacktrace=never`.

## Created with Location

```java
@PostMapping("/orders")
ResponseEntity<OrderDto> create(@Valid @RequestBody CreateOrder req, UriComponentsBuilder uri) {
    Order o = service.create(req);
    return ResponseEntity.created(uri.path("/orders/{id}").build(o.id())).body(OrderDto.from(o));
}
```

## Cursor pagination with a cap

```java
record CursorPage<T>(List<T> items, String next) {}      // next: opaque, null on the last page

@Validated                                                // needed for @Max on a parameter before Spring 6.1
@RestController
class OrderController {
    @GetMapping("/orders")
    CursorPage<OrderDto> list(@RequestParam(required = false) String cursor,
                              @RequestParam(defaultValue = "50") @Min(1) @Max(200) int limit) {
        return service.page(cursor, limit);               // keyset query: WHERE id > :after ORDER BY id LIMIT :limit
    }
}
// response: { "items": [ … ], "next": "eyJpZCI6IjEyMyJ9" }
```

Not Spring Data's `Page<T>`: it serialises offset metadata (`totalElements`, `totalPages`) and runs a count query on every call. For keyset paging in Spring Data use `ScrollPosition` and `Window<T>` (3.1+), mapped to the envelope above; `spring.data.web.pageable.max-page-size=200` caps `Pageable` where offset paging is kept.

## Conditional update (lost-update protection)

```java
@GetMapping("/orders/{id}")
ResponseEntity<OrderDto> get(@PathVariable String id) {
    Order o = service.get(id);
    return ResponseEntity.ok().eTag("\"" + o.version() + "\"").body(OrderDto.from(o));
}

private static final Pattern STRONG_ETAG = Pattern.compile("\"(\\d{1,18})\"");

@PutMapping("/orders/{id}")
ResponseEntity<OrderDto> put(@PathVariable String id,
                             @RequestHeader(value = "If-Match", required = false) String ifMatch,
                             @Valid @RequestBody OrderDto body) {
    if (ifMatch == null) {
        return ResponseEntity.status(HttpStatus.PRECONDITION_REQUIRED).build();      // 428
    }
    Long expected = null;                                  // "*": any current version matches (RFC 9110)
    if (!ifMatch.strip().equals("*")) {
        Matcher m = STRONG_ETAG.matcher(ifMatch.strip());  // one strong ETag; weak (W/"…") or a list never matches
        if (!m.matches()) {
            return ResponseEntity.status(HttpStatus.PRECONDITION_FAILED).build();    // 412
        }
        expected = Long.parseLong(m.group(1));
    }
    Order o = service.replace(id, body, expected);        // UPDATE … WHERE version = ?; 0 rows → 412; 404 if absent
    return ResponseEntity.ok().eTag("\"" + o.version() + "\"").body(OrderDto.from(o));
}
```

A list of ETags (`"1", "2"`) is legal in `If-Match`; this example treats it as no match (412), which is safe. Support it only if clients send it.

## Idempotency-Key on POST

1. Client sends `Idempotency-Key: <uuid>`.
2. Server looks up the key (scoped to the caller): not seen → record it as in-flight with a fingerprint of the request body, process, store the response; in flight → 409; done with the same fingerprint → return the stored response; done with a different fingerprint → 422.
3. Expire keys after a documented window (24 hours is common). If processing ends with an unknown outcome, keep the key; don't free it for a retry that may double-charge.

## Express and FastAPI

- Express: one error middleware `(err, req, res, next)` that sets `res.type('application/problem+json')`; validation with the project's validator (zod, joi, express-validator); `helmet` for headers; `express.json({ limit: '100kb' })`.
- FastAPI: Pydantic models with `Field(max_length=…)`, `status_code=201` on create routes, an `exception_handler` for `RequestValidationError` returning problem details; `response_model` so only declared fields are returned.
