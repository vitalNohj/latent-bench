# latent-bench report: pilot

focus arm: `latent`

generated 2026-10-09 11:19. gen model `claude-opus-5-5 (via private proxy)` (thinking off), judge `gpt-6.1-sol (via private proxy)`. 15 prompts; replies per arm below.

skill versions: latent `c487577d5e1e`, caveman `5e30bb56afbd`

## Per arm

| arm | replies | visible tok | visible vs base | billed tok | billed vs base | secs | in tok/call | core cov | all cov | errors/reply | qualifiers/100w | social | offer | hedge | meta | headers | bold |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 30 | 432 | 100% | 739 | 100% | 8.8 | 819 | 98% | 96% | 0.70 | 2.13 | 0.13 | 0.00 | 0.03 | 0.00 | 3.00 | 6.93 |
| terse | 30 | 267 | 62% | 454 | 61% | 6.1 | 827 | 95% | 92% | 0.57 | 2.23 | 0.07 | 0.00 | 0.00 | 0.00 | 0.07 | 6.70 |
| caveman | 30 | 373 | 86% | 653 | 88% | 8.3 | 2711 | 98% | 94% | 0.90 | 1.62 | 0.00 | 0.00 | 0.07 | 0.00 | 0.50 | 4.77 |
| latent | 30 | 370 | 86% | 709 | 96% | 9.6 | 5385 | 98% | 96% | 0.90 | 1.11 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.33 |

visible tok: o200k_base count of the reply text, a proxy tokenizer (needs tiktoken: `uv run bench.py`). billed tok: `usage.output` from the API. Billed exceeds visible by generation the API does not return, even with thinking off; it adds latency, so it is real compute, not rounding.

core cov / all cov: share of key points the judge found conveyed (core points only / all points). errors/reply: judge-flagged wrong or misleading claims. qualifiers/100w: scope words such as usually, by default, can, depends, unless, in prose outside code fences. social, offer, hedge, meta, headers, bold: regex hits per reply.

## latent vs other arms (paired per prompt, 95% bootstrap CI over prompts)

| vs | core cov Δ | all cov Δ | errors/reply Δ | visible tok, latent / other | billed tok, latent / other |
|---|---|---|---|---|---|
| base | +0.0 pp [+0.0, +0.0] | -0.1 pp [-2.8, +2.8] | +0.20 [-0.27, +0.67] | 0.97x [0.84, 1.14] | 1.01x [0.91, 1.13] |
| terse | +3.1 pp [+0.0, +6.4] | +4.2 pp [+1.2, +7.5] | +0.33 [-0.13, +0.80] | 1.57x [1.33, 2.02] | 1.62x [1.45, 1.82] |
| caveman | +0.6 pp [+0.0, +1.7] | +1.7 pp [-1.0, +4.5] | +0.00 [-0.47, +0.50] | 1.10x [0.96, 1.34] | 1.18x [1.02, 1.40] |

token ratios: geometric mean over prompts.

## Pairwise preference (judge sees both replies, both orders)

| pair | first arm score | 95% CI | wins | ties | losses | judgments | order flips |
|---|---|---|---|---|---|---|---|
| latent vs base | 0.62 | [0.43, 0.80] | 37 | 0 | 23 | 60 | 3/30 |
| latent vs terse | 0.52 | [0.33, 0.68] | 31 | 0 | 29 | 60 | 7/30 |
| latent vs caveman | 0.53 | [0.33, 0.72] | 32 | 0 | 28 | 60 | 6/30 |
| caveman vs terse | 0.43 | [0.28, 0.58] | 25 | 2 | 33 | 60 | 9/30 |

score = (wins + ties/2) / judgments for the first arm; CI bootstraps prompts. order flips = items where swapping A/B changed the verdict.

## Per prompt: visible tokens · core coverage

| prompt | category | base | terse | caveman | latent |
|---|---|---|---|---|---|
| idem-key | concept | 699 · 100% | 371 · 100% | 444 · 100% | 523 · 100% |
| strict-mode | debug-shorthand | 396 · 100% | 223 · 100% | 403 · 100% | 349 · 100% |
| utf16-csv | debug-error | 292 · 100% | 261 · 100% | 269 · 100% | 292 · 100% |
| sqlite-vs-pg | decision | 320 · 100% | 182 · 83% | 300 · 92% | 318 · 100% |
| git-undo | procedure | 120 · 88% | 90 · 75% | 116 · 88% | 171 · 88% |
| drop-prod | destructive | 443 · 83% | 272 · 67% | 341 · 83% | 486 · 83% |
| jwt-storage | security | 406 · 100% | 248 · 100% | 348 · 100% | 327 · 100% |
| sqli-review | code-review | 278 · 100% | 195 · 100% | 335 · 100% | 280 · 100% |
| winston-p99 | performance | 760 · 100% | 445 · 100% | 612 · 100% | 510 · 100% |
| flag-names | creative | 90 · 100% | 77 · 100% | 98 · 100% | 102 · 100% |
| pg-port | trivial | 13 · 100% | 4 · 100% | 10 · 100% | 30 · 100% |
| exit-137 | debug-shorthand | 550 · 100% | 350 · 100% | 454 · 100% | 450 · 100% |
| ci-speed | brainstorm | 816 · 100% | 484 · 100% | 702 · 100% | 580 · 100% |
| race-simple | plain-wording | 468 · 100% | 297 · 100% | 338 · 100% | 389 · 100% |
| docker-slim | shorthand-slots | 824 · 100% | 512 · 100% | 823 · 100% | 748 · 100% |

## Multi-turn drift (skill invoked on turn 1 only)

| turn | question | base vis tok | terse vis tok | caveman vis tok | latent vis tok | base reg | terse reg | caveman reg | latent reg |
|---|---|---|---|---|---|---|---|---|---|
| 1 | our postgres queries got slow after a migration.… | 612 | 423 | 578 | 527 | 1.0 | 1.0 | 1.5 | 1.0 |
| 2 | the migration added a column and an index on ord… | 732 | 502 | 526 | 609 | 0.0 | 0.0 | 2.0 | 2.0 |
| 3 | how do i check whether the planner actually uses… | 760 | 422 | 615 | 530 | 0.5 | 1.0 | 2.0 | 2.0 |
| 4 | it uses it, but the query still takes 2s. the ta… | 880 | 598 | 772 | 650 | 0.0 | 0.5 | 2.0 | 2.0 |
| 5 | unrelated: what's the difference between a proce… | 320 | 219 | 286 | 402 | 1.0 | 1.0 | 2.0 | 3.0 |
| 6 | thanks, that helps! can you give me a bash one-l… | 234 | 132 | 171 | 250 | 1.0 | 0.5 | 2.0 | 2.5 |
| 7 | last one: should we upgrade from postgres 14 to … | 514 | 350 | 480 | 674 | 0.0 | 1.0 | 1.5 | 2.0 |

reg = judge register score: 0 ordinary prose … 3 compressed throughout.

| arm | conversations | visible tok / convo | billed tok / convo | social turns | offer turns | meta turns |
|---|---|---|---|---|---|---|
| base | 2 | 4052 | 7958 | 0/14 | 4/14 | 0/14 |
| terse | 2 | 2646 | 5550 | 0/14 | 3/14 | 0/14 |
| caveman | 2 | 3428 | 7256 | 0/14 | 1/14 | 0/14 |
| latent | 2 | 3642 | 8954 | 0/14 | 0/14 | 0/14 |

## Judge-flagged errors (verify by hand: the judge can be wrong)

- base / ci-speed / s1: GitHub Actions has no top-level `on.paths` filter; path filters belong under events such as `on.pull_request.paths` or `on.push.paths`.
- base / ci-speed / s1: Enabling GitHub merge queue does not automatically replace full-suite runs on every PR push with a single pre-merge run. Workflows must be configured accordingly, and merge-queue checks can run again when merge groups change.
- base / docker-slim / s1: The package-size command leaves the wildcard unquoted and runs no shell inside the container, so the host shell expands it rather than the container shell; it will not reliably measure the container's site-packages.
- base / docker-slim / s1: pipdeptree shows dependency relationships, but does not determine whether dependencies are unused.
- base / drop-prod / s0: GRANT ALL ON SCHEMA public TO public does not generally restore default permissions. In PostgreSQL 15+ newly created databases, PUBLIC normally has USAGE but not CREATE on the public schema; this command grants CREATE to every role.
- base / drop-prod / s1: GRANT ALL ON SCHEMA public TO public does not restore the schema's original grants and grants CREATE to every role; this is broader than PostgreSQL 15+ defaults.
- base / exit-137 / s0: SIGKILL does not imply the process never had a chance to write logs; it prevents logging or cleanup after the signal, but earlier output may exist.
- base / exit-137 / s1: SIGKILL does not necessarily explain empty logs: output already written to stdout/stderr should remain available, though buffered output may be lost.
- base / exit-137 / s1: The claim that ignoring SIGTERM only matters on shutdown, not in a crash loop, is incorrect: repeated liveness-probe failures can trigger termination, followed by SIGKILL after the grace period, and produce a crash loop.
- base / race-simple / s0: The outcome depends on the ordering or interleaving of operations, not necessarily on which worker finishes first.
- base / race-simple / s0: Atomic operations are indivisible as observed by other threads, but are not necessarily guaranteed to execute without interruption.
- base / sqli-review / s1: The claim that "1; DROP TABLE users" gets executed is too broad: stacked statements depend on the driver and configuration; sqlite3.execute, for example, rejects multiple statements.
- base / sqlite-vs-pg / s0: Using an ORM or query builder does not make SQLite-to-Postgres migration mostly a data copy; schema, data types, SQL behavior, and application assumptions may still require changes.
- base / sqlite-vs-pg / s1: User count alone does not establish write load; 20 users can generate heavy concurrent writes, and SQLite's write throughput depends on workload and hardware.
- base / sqlite-vs-pg / s1: Calling synchronous=NORMAL 'safe with WAL' is incomplete: it preserves database consistency, but recently committed transactions can be lost after a power failure or OS crash.
- base / sqlite-vs-pg / s1: An ORM or query builder does not necessarily make SQLite-to-Postgres migration fairly painless; schema, typing, SQL behavior, and data migration can still require substantial work.
- base / winston-p99 / s0: On Linux/POSIX, process.stdout writes to pipes are asynchronous, not synchronous. Docker/Kubernetes commonly use pipes, so collector backpressure does not necessarily block the event loop synchronously.
- base / winston-p99 / s0: Pino's standard asynchronous destinations and worker-thread transports offload output processing/I/O, but ordinary log-object serialization still happens on the main thread.
- base / winston-p99 / s0: High event-loop delay alone does not prove logging is blocking; it indicates event-loop stalls whose cause must be established through profiling or comparison with logging disabled.
- base / winston-p99 / s1: On Linux/POSIX, process.stdout writes are asynchronous when stdout is a pipe, not synchronous as claimed. Writes to regular files and TTYs are synchronous; slow Docker/k8s pipe consumers can cause backpressure without each write directly blocking the event loop.
- base / winston-p99 / s1: Multiple Winston transports do not necessarily each repeat formatting. Logger-level formatting runs before dispatch to transports; additional per-transport formatting occurs only when configured.
- caveman / docker-slim / s0: The slim image does not remove only build tooling and documentation; it also omits many system utilities and libraries present in the full image, so additional runtime packages may be needed.
- caveman / docker-slim / s1: Unqualified python:3.12 and python:3.12-slim tags do not guarantee Debian Bookworm. To preserve the existing Debian release, inspect the current base and pin the matching distro-specific slim tag rather than assuming Bookworm.
- caveman / drop-prod / s0: Option 2 does not guarantee preserving functions and types: DROP TABLE ... CASCADE can also drop dependent objects, including functions that depend on a table's row type.
- caveman / drop-prod / s0: GRANT ALL ON SCHEMA public TO public does not generally restore the original or default grants; notably, it grants CREATE to everyone, which is not the default for newly created databases in PostgreSQL 15 and later.
- caveman / drop-prod / s1: The tables-only method does not necessarily keep all functions and types: DROP TABLE ... CASCADE can also drop dependent functions and types, including each table's associated row type.
- caveman / exit-137 / s0: A heap limit larger than the container memory limit does not necessarily cause an instant startup OOM; the kill depends on actual memory consumption, not merely the configured maximum heap size.
- caveman / exit-137 / s1: Modern JVMs generally detect container memory limits automatically; setting MaxRAMPercentage or Xmx is not required for container awareness.
- caveman / exit-137 / s1: A termination reason of Error with exit code 137 does not rule out an OOM kill; the runtime may not identify every OOM kill as OOMKilled.
- caveman / exit-137 / s1: A failed liveness probe does not necessarily produce exit code 137: termination normally starts with SIGTERM, with SIGKILL only if the container fails to exit within the grace period.
- caveman / git-undo / s1: Resetting a pushed commit does not necessarily cause conflicts for others pulling; it can cause divergent histories or require reconciliation.
- caveman / git-undo / s1: git revert HEAD reverses the commit's changes rather than preserving them staged or unstaged, so it is not a direct substitute for the requested operation.
- caveman / idem-key / s0: The claim that the network provides at-least-once delivery is incorrect: networks can lose requests entirely. At-least-once delivery requires a retry or delivery mechanism, not merely a network.
- caveman / jwt-storage / s1: The claim that XSS can send authenticated requests 'only while the page is open' is misleading. XSS can make lasting account changes, establish persistent access, or potentially install a malicious service worker; HttpOnly prevents direct cookie reads, not these effects.
- caveman / race-simple / s0: The JavaScript example is misleading as executable code: ordinary JavaScript threads do not share a plain `let count` variable, and synchronous calls to `increment()` cannot interleave this way. It works as pseudocode for threads sharing memory, not as shown in standard JavaScript.
- caveman / race-simple / s1: The JavaScript example is misleading: ordinary JavaScript variables are not shared between worker threads, and this synchronous increment function runs to completion on a single thread. As written, two calls do not produce the claimed lost update; a JavaScript example would need shared memory or asynchronous interleaving.
- caveman / sqli-review / s0: Parameterized queries bind values as data; saying the driver simply 'escapes' the value is misleading and driver-dependent.
- caveman / sqli-review / s0: The claim that an injected '1; DROP TABLE users; --' gets executed is too categorical: stacked-statement execution depends on the database driver, API, and configuration.
- caveman / sqli-review / s1: The claim that an attacker can use `1; DROP TABLE users;--` to run arbitrary SQL is driver-dependent. For example, sqlite3.execute() rejects multiple statements, although the original query remains vulnerable to SQL injection.
- caveman / sqlite-vs-pg / s0: busy_timeout=5000 waits up to five seconds for certain lock conflicts; it does not guarantee prevention of 'database is locked' errors, even under light contention.
- caveman / sqlite-vs-pg / s0: Using an ORM or query builder does not guarantee a cheap migration to Postgres; schema, data types, SQL behavior, and application assumptions can still require substantial changes.
- caveman / sqlite-vs-pg / s1: The claim that concurrent writes throw 'database is locked' without WAL plus busy_timeout is too categorical: writes can succeed without these settings, and lock errors can still occur with them.
- caveman / sqlite-vs-pg / s1: Twenty users does not guarantee a light write workload; SQLite's suitability and write throughput depend on transaction duration, write frequency, hardware, and contention.
- caveman / sqlite-vs-pg / s1: Using an ORM or query builder and avoiding dialect-specific SQL does not guarantee a cheap migration to Postgres; schemas, types, concurrency behavior, and application assumptions can still require significant changes.
- caveman / utf16-csv / s1: The claim that the file is definitely UTF-16 is not justified by a leading 0xFF alone. Confirm the full byte sequence; even FF FE can begin a UTF-32 LE BOM (FF FE 00 00).
- caveman / winston-p99 / s0: The stdout behavior is misstated: Node stdout writes to pipes are asynchronous on POSIX, not synchronous. TTY writes are synchronous on POSIX but asynchronous on Windows. A slow Docker logging pipe can cause backpressure, but does not inherently make each stdout write synchronously block.
- caveman / winston-p99 / s1: Node stdout writes to pipes are asynchronous on Linux/POSIX, not synchronous. TTY writes are synchronous on POSIX but asynchronous on Windows.
- caveman / winston-p99 / s1: Winston's logger-level format pipeline runs once per log entry, not once per transport; only transport-specific format pipelines run separately per transport.
- latent / ci-speed / s0: CPU-bound steps do not generally scale near-linearly with core count; additional cores help only when the workload can effectively use them.
- latent / ci-speed / s0: Config-only changes are not generally safe grounds for skipping heavy jobs; build, compiler, dependency, or test configuration changes can affect the entire monorepo.
- latent / ci-speed / s1: Blanket skipping of test jobs for config-only PRs is unsafe: configuration changes can affect builds, runtime behavior, or tests and may require validation.
- latent / docker-slim / s0: The claim that Alpine 'breaks musl wheels' is incorrect: Alpine uses musl and supports compatible musllinux wheels. The usual compatibility issue is with glibc-based manylinux wheels.
- latent / docker-slim / s1: Lacking manylinux wheels does not necessarily require a builder stage, and Alpine does not invariably force source builds: pure-Python wheels and compatible musllinux wheels can be installed directly.
- latent / drop-prod / s0: Option A does not preserve grants on dropped tables. CASCADE can also remove dependent functions and other objects, so its claim to preserve functions and types is too broad.
- latent / drop-prod / s0: Tables outside public are not necessarily untouched: dropping a partitioned table in public also drops its partitions, including partitions in other schemas.
- latent / drop-prod / s1: The “Tables only, keep everything else” description is misleading: DROP TABLE ... CASCADE also removes dependent objects such as views and foreign-key constraints, and dropping tables removes their indexes, triggers, and owned sequences.
- latent / exit-137 / s1: An OOMKilled reason confirms an OOM kill, but does not by itself prove the container exceeded its own memory limit; node-wide OOM can also cause it.
- latent / exit-137 / s1: kubectl top pod reports recent memory usage, not peak usage; it can miss the spike that killed a container. Peak measurement requires historical metrics sampled frequently enough.
- latent / exit-137 / s1: A failing sidecar or init container does not ordinarily cause the application container to receive SIGKILL; listing this as a generic SIGKILL cause is misleading.
- latent / git-undo / s1: The claim that --hard deletes any uncommitted work is too broad: it discards tracked-file changes, but generally leaves untracked files alone unless they obstruct checkout.
- latent / idem-key / s1: The claim that reusing a key across different charges silently swallows the second charge is too broad: if the request parameters differ, the server generally rejects the reuse rather than replaying the first result.
- latent / idem-key / s1: The unconditional 'at most once, no matter how many times it is retried' guarantee is overstated: after the key expires, retrying with that key can execute the operation again.
- latent / jwt-storage / s0: The table incorrectly says cross-domain cookie authentication requires a shared site. Cross-site cookies can work with SameSite=None; Secure and credentialed CORS, subject to browser third-party-cookie restrictions.
- latent / jwt-storage / s1: The table implies cookie authentication for a cross-domain API requires the API to be same-site. Cross-site cookie authentication is possible with SameSite=None; Secure and credentialed CORS, subject to browser third-party-cookie restrictions.
- latent / jwt-storage / s1: The table implies cookie-based authentication always requires both SameSite and a CSRF token. Appropriate SameSite protections can suffice in some designs; both are not universally required.
- latent / sqlite-vs-pg / s0: Using an ORM or query builder does not make switching from SQLite to Postgres just a configuration change plus data copy; schema types, migrations, queries, and database-specific behavior may also need changes.
- latent / sqlite-vs-pg / s1: busy_timeout=5000 waits up to five seconds for a lock; it does not guarantee that writes will queue successfully rather than fail with SQLITE_BUSY.
- latent / strict-mode / s0: Recommending a useRef flag for once-only work is misleading: it can suppress StrictMode's setup rerun without fixing cleanup, and it does not prevent the work from repeating after a real remount.
- latent / strict-mode / s0: The claim that a POST necessarily belongs in an event handler rather than useEffect is too broad; some POST requests legitimately synchronize with component state and require appropriate deduplication or server-side idempotency.
- latent / utf16-csv / s0: A leading 0xFF alone does not establish that the file is UTF-16 LE; the opening assertion is too definite.
- latent / utf16-csv / s0: FF FE can also begin a UTF-32 LE BOM, so it does not by itself conclusively confirm UTF-16 LE.
- latent / utf16-csv / s0: An initial FF not followed by FE does not rule out UTF-16, which can exist without a BOM.
- latent / utf16-csv / s0: open() does not universally default to UTF-8; its default encoding depends on the Python version, locale, and UTF-8 mode.
- latent / winston-p99 / s0: On Linux/POSIX, process.stdout writes to pipes and sockets are asynchronous, not synchronous. Writes to regular files and terminals are synchronous, so Docker or Kubernetes log pipes do not inherently block the event loop as claimed.
- latent / winston-p99 / s1: On Linux, process.stdout writes to pipes are asynchronous, not synchronous. Writes to regular files are synchronous, so grouping Docker/k8s/pm2 pipes with files and claiming they all block until each log line is flushed is incorrect.
- terse / ci-speed / s0: A merge queue does not inherently make the full suite run only once at merge instead of on every push; that requires workflow configuration, and queue updates can trigger additional runs.
- terse / docker-slim / s0: Copying /wheels into the runtime image and deleting them in a subsequent RUN does not remove their bytes from the earlier COPY layer, so the wheels still increase the final image size.
- terse / drop-prod / s0: The 'Tables only (keeps functions and types)' claim is not guaranteed: DROP TABLE ... CASCADE can also remove dependent functions and types, as well as views.
- terse / exit-137 / s1: Being killed externally with SIGKILL does not inherently make logs empty; output already written to stdout/stderr should still be available.
- terse / git-undo / s1: git revert HEAD creates a new commit that reverses the changes; it does not undo the commit while keeping its changes staged or unstaged.
- terse / race-simple / s0: A race condition depends on the ordering or interleaving of operations, not necessarily on which concurrent task finishes first.
- terse / sqli-review / s0: The claim that `1; DROP TABLE users` runs as SQL is driver-dependent; many database drivers reject multiple statements in a single execute call.
- terse / sqli-review / s1: The claim that `1; DROP TABLE users` would execute is driver-dependent; many database APIs reject multiple statements in a single execute call.
- terse / sqli-review / s1: `SELECT *` does not necessarily break when the schema changes, though changes can break callers that depend on the returned columns or their order.
- terse / sqlite-vs-pg / s0: With WAL enabled, copying only the main database file is not a safe backup of a live database: committed data may still be in the WAL file. Use SQLite's backup API or a properly coordinated checkpoint and copy.
- terse / sqlite-vs-pg / s1: Copying only the SQLite database file is not a safe backup while writes are occurring, especially in WAL mode; use SQLite's backup API or a coordinated snapshot.
- terse / sqlite-vs-pg / s1: Using an ORM or query builder does not guarantee a painless migration to Postgres; schema, SQL, data types, and database behavior may still require changes.
- terse / strict-mode / s1: Recommending a useRef flag for one-time effects is misleading: it can mask StrictMode’s cleanup checks rather than make the effect safe to rerun, and it does not prevent execution on a genuine remount.
- terse / winston-p99 / s0: Node stdout writes to pipes are asynchronous on POSIX and synchronous on Windows; the blanket claim that piped stdout is synchronous is incorrect.
- terse / winston-p99 / s0: Winston's built-in File transport normally uses asynchronous stream writes, so describing it as a synchronous event-loop blocker is misleading.
- terse / winston-p99 / s0: Winston's logger.log() normally returns the logger, not a promise for transport completion. Awaiting it does not ordinarily wait for a network round trip.
- terse / winston-p99 / s1: The claim that console output to a pipe is synchronous and that Docker/systemd capture makes every logger.info block is incorrect as a blanket statement. Node stdout behavior depends on the platform and destination: on POSIX, pipe/socket writes are asynchronous, while file writes are synchronous. Logging can still cause CPU overhead and backpressure without each write synchronously blocking.
