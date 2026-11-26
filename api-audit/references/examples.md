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
@GetMapping("/orders")
Page<OrderDto> list(@RequestParam(required = false) String cursor,
                    @RequestParam(defaultValue = "50") @Max(200) int limit) { … }
// response: { "items": [ … ], "next": "eyJpZCI6IjEyMyJ9" }   // opaque, null on the last page
```

Spring Data: `spring.data.web.pageable.max-page-size=200` caps `Pageable`; keyset with `ScrollPosition` / `Window` (Spring Data 3.1+).

## Conditional update (lost-update protection)

```java
@GetMapping("/orders/{id}")
ResponseEntity<OrderDto> get(@PathVariable String id) {
    Order o = service.get(id);
    return ResponseEntity.ok().eTag("\"" + o.version() + "\"").body(OrderDto.from(o));
}

@PutMapping("/orders/{id}")
ResponseEntity<OrderDto> put(@PathVariable String id, @RequestHeader("If-Match") String ifMatch,
                             @Valid @RequestBody OrderDto body) {
    long expected = Long.parseLong(ifMatch.replace("\"", ""));
    Order o = service.replace(id, body, expected);        // UPDATE … WHERE version = ?; 0 rows → 412
    return ResponseEntity.ok().eTag("\"" + o.version() + "\"").body(OrderDto.from(o));
}
```

## Idempotency-Key on POST

1. Client sends `Idempotency-Key: <uuid>`.
2. Server looks up the key (scoped to the caller): not seen → record it as in-flight with a fingerprint of the request body, process, store the response; in flight → 409; done with the same fingerprint → return the stored response; done with a different fingerprint → 422.
3. Expire keys after a documented window (24 hours is common). If processing ends with an unknown outcome, keep the key; don't free it for a retry that may double-charge.

## Express and FastAPI

- Express: one error middleware `(err, req, res, next)` that sets `res.type('application/problem+json')`; validation with the project's validator (zod, joi, express-validator); `helmet` for headers; `express.json({ limit: '100kb' })`.
- FastAPI: Pydantic models with `Field(max_length=…)`, `status_code=201` on create routes, an `exception_handler` for `RequestValidationError` returning problem details; `response_model` so only declared fields are returned.
