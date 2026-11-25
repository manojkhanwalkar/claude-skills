# Examples: good and bad doc comments

Java unless marked. Each "bad" shows a mistake this skill must not make or must fix.

## Class comments

**Bad: restates the name, says nothing about role.**

```java
/**
 * The AlertMailer class.
 */
public class AlertMailer {
```

**Bad: narrates the implementation.**

```java
/**
 * This class has a constructor that takes a repo and a client. Then the sendDue method
 * loops over the alerts and for each one it calls the client and then it updates the repo.
 */
```

**Good: role, collaborators, invariant, thread safety.**

```java
/**
 * Sends alert emails for new credit alerts, at most once per alert.
 *
 * <p>The daily {@code NotifierJob} calls {@link #sendDue(Instant)}. Alerts are claimed in
 * {@link AlertRepo} before sending, so a second run never emails the same alert; a send
 * that fails releases its claim for the next run. Thread-safe; one shared instance.
 */
public class AlertMailer {
```

## Method comments

**Bad: obvious, on an exempt getter.** Delete nothing that is there and accurate, but never add this:

```java
/**
 * Gets the email.
 *
 * @return the email
 */
public String getEmail() { return email; }
```

**Bad: invented claim.** The method doesn't retry; the comment says it does.

```java
/** Sends the email, retrying three times on failure. */
public void send(Email e) { client.send(e); }
```

**Good: what, why, parameters, return, exceptions, side effects, edge cases.**

```java
/**
 * Claims the alerts due at {@code now} and emails each subscriber once.
 *
 * <p>Reads at most {@code maxAlertsPerRun} alerts; the rest stay unclaimed for the next
 * run. Non-subscribers' alerts are claimed and skipped, so they aren't read again.
 *
 * @param now the run's clock reading; alerts older than {@code now - lookback} are ignored
 * @return the number of emails sent, zero when nothing was due
 * @throws NotificationException when the notification service rejects the batch; claims
 *     made in this run are released first
 */
public int sendDue(Instant now) {
```

**Python, good (PEP 257, imperative summary):**

```python
def mask_ssn(ssn: str) -> str:
    """Return the SSN with all but the last four digits replaced by '*'.

    Raises:
        ValueError: when ``ssn`` is not nine digits, with or without dashes.
    """
```

## Standardising

**Before: a `//` block describing the method, tags in the wrong order, code as plain text.**

```java
// Finds the alerts for a user. Returns null if user is null.
/**
 * @throws IllegalStateException if the table is missing
 * @return list of alerts
 * @param userId
 */
public List<Alert> findForUser(String userId) {
```

**After: one Javadoc, summary first, tags in order, empty tag filled from the code, `{@code}`.**

```java
/**
 * Finds a user's alerts, newest first.
 *
 * @param userId the user's ID; {@code null} gives an empty list
 * @return the alerts, never {@code null}
 * @throws IllegalStateException if the Alerts table is missing
 */
public List<Alert> findForUser(String userId) {
```

(The old `//` line said "returns null"; the code returns an empty list. The new text follows the code.)

## Stale comments

**Before, after a PR changed the default from 50 to 100 and removed the `force` parameter:**

```java
/**
 * Sends up to 50 alerts.
 *
 * @param force send even if already claimed
 */
public int sendBatch() {
```

**After:**

```java
/**
 * Sends up to {@code maxBatch} alerts (100 by default).
 */
public int sendBatch() {
```

When the right text isn't clear from the code, delete the false sentence, keep the rest, and flag it in the report rather than guess.

## Matching the house style

CreditAgent's records document configuration in `@param` lines that are lower-case fragments, explain defaults and the reason for a limit, and use `{@code}` for property names and literals:

```java
/**
 * The alert notifier ({@code credit.notifier.*}).
 *
 * @param lookback how far back a run looks for alerts no email has covered yet
 * @param maxAlertsPerRun most alerts one run reads; the rest stay unclaimed for the next run
 * @param dynamodbEndpoint blank = AWS; {@code http://localhost:8000} for DynamoDB Local
 */
```

A new component added to that record gets a `@param` in the same voice, not a full sentence with "This parameter specifies...".
