# repo2ree - Engineering Test Guide

> Status: current test layout (2026-06). The suite intentionally separates
> container-free checks from Docker-gated integration and e2e flows.

## Quick Map

| Target | What it runs |
|---|---|
| `make gui-checks` | GUI TypeScript, Biome, knip, dependency-cruiser. |
| `make gui-tests` | GUI Vitest tests. |
| `make be-checks` | Ruff, Ruff format, and mypy across Python workspace packages. |
| `make scripts-checks` | ShellCheck over `scripts/*.sh`. |
| `make be-unit-tests` | Container-free backend unit tests. |
| `make be-integration-tests` | Integration tiers, including Docker-gated workbench tests when Docker and the image exist. |
| `make be-tests` | Backend unit plus integration tests. |
| `make e2e-tests` | Playwright e2e project against a live API and GUI dev server. |
| `make e2e-review` | Playwright review project: the reviewer-side reproduction specs. |
| `make e2e-demo` | Playwright demo walkthrough project with video. |
| `make e2e-tests-images` / `e2e-review-images` / `e2e-demo-images` | Suite / review / demo against an already-running image-backed stack. |
| `make e2e-tests-stack` / `e2e-review-stack` / `e2e-demo-stack` | One command: build local images, `stack-up`, run the project, `stack-clean`. |
| `make e2e-tests-stack-published` / `e2e-review-stack-published` / `e2e-demo-stack-published` | The same flows against the pushed registry images (nothing built). |
| `make stack-up` / `stack-down` | Start/stop the image-backed stack, keeping its volumes (`scripts/image-stack.sh`). |
| `make stack-clean` | Stop it and drop every volume it created, workbench leftovers included. |
| `make workbench-clean` | Just the workbench leftovers; `STORE=1` also drops every bundle store volume. |
| `make store-gc` | Evict bundle store caches unused for `STORE_GC_DAYS` (14), keeping the live one. |
| `make commit-gate` | Fast pre-commit gate: static checks + all container-free test tiers. Certifies the tree it passed on; the pre-commit hook checks that certificate. |
| `make push-gate` | The pre-publish gate: clean tree, all checks and tests, e2e source-run and image-backed. |
| `make coverage-unit` / `coverage-integration` / `coverage-e2e` / `coverage-demo` | Coverage for one tier, into its own report. `coverage-e2e` / `coverage-demo` also produce browser-side GUI coverage. |
| `make coverage-combined` | Union of whichever tiers have been measured on this checkout. |
| `make coverage-context` | Per-test coverage attribution over the two pytest tiers. |

## Before Docker-Gated Tests

Build the executor/tools bundles the agent injects into benches:

```bash
make e2e-bundles
```

The Docker-gated tiers skip when Docker or the bundles are absent. They do
not fake the workbench path; the first run pulls the pinned `docker:dind`
bench image.

## Backend Checks

Run all Python static checks:

```bash
make be-checks
```

Per-package targets are available:

```bash
make protocol-checks
make core-checks
make supervisor-checks
make api-checks
make executor-checks
```

These targets run `ruff check`, `ruff format`, and `mypy` for their package.
They may modify formatting.

## Backend Tests

Fast, container-free tests:

```bash
make be-unit-tests
```

Full backend test suite:

```bash
make be-tests
```

Per-package test targets:

```bash
make core-tests
make api-tests
make supervisor-tests
make executor-tests
```

Important split:

- `core/tests/unit` and `api/tests/unit` are regular unit tests.
- `core/tests/integration` exercises the real command handlers against a temp
  REE tree, without Docker.
- `api/tests/integration` runs the real FastAPI app over HTTP against real
  workbench containers.
- `supervisor/tests/integration` provisions a real workbench and drives the
  real `docker exec -> repo2ree-exec -> core` path.

Do not run `pytest api/tests` as one process. The API unit and integration
tiers intentionally run separately because OpenTelemetry's tracer provider is
process-global. Use:

```bash
make api-unit-tests
make api-integration-tests
```

or:

```bash
pytest api/tests/unit
pytest api/tests/integration
```

## Coverage

Coverage is measured per **tier**, one report each, matching the four ways this
project is tested:

| Tier | Target | What it measures | Needs |
|---|---|---|---|
| `unit` | `make coverage-unit` | Container-free suites | nothing |
| `integration` | `make coverage-integration` | Docker-gated suites | docker + bundles |
| `e2e` | `make coverage-e2e` | The live stack, browser-driven | docker + browsers |
| `demo` | `make coverage-demo` | The narrated walkthrough stack | docker + browsers |

Each tier writes its data to `test-artifacts/coverage/data/<tier>/` and its HTML
report to `test-artifacts/coverage/<tier>/`, so a tier's number always means
"what this way of testing reaches" and never a blend of two.

### By module

Every tier is also broken down by source package, into
`test-artifacts/coverage/<tier>/by-module/<package>/`, and each run prints the
per-package totals:

```
>> unit tier, by module
   protocol     99%
   core         90%
   supervisor   82%
   api          86%
   executor     81%
   agent        70%
   TOTAL        88%
```

These are filters over the tier's own data, not separate runs — so they cost no
extra test time and exist for every tier, including `e2e` and `demo`, which are
a single stack run and could never be decomposed by suite. They answer "how
well covered is this package", with every suite in the tier contributing.

Comparing one package across tiers is often the useful read: `agent` is 70% in
`unit` and 87% in `combined`, because its docker runtime only runs under the
stack tiers.

All of this lives in `mk/tests.mk`: the tier definitions, the package list
(`COVERAGE_PACKAGES`), and the `coverage_render` rule every tier reports
through. To re-render a tier from data already measured, without repeating its
suite:

```bash
make coverage-report TIER=unit
```

Union of whatever has been measured:

```bash
make coverage-combined
```

It skips tiers that were never run, so it is useful after any subset — but the
combined number is only the honest total when every tier ran on the same tree,
which is what `push-gate` arranges. `--keep` means combining never destroys the
per-tier data, so any tier report can be rebuilt without re-running its suite.

Per-test attribution (which test hit which line) over the two pytest tiers:

```bash
make coverage-context
```

Two things to know when reading a report:

- **The `unit` tier is a floor, not the truth.** The docker-gated transport
  (supervisor manager, hbom profilers, the agent's docker runtime) is not
  exercised there, so it reads as uncovered. That is what the `integration`
  tier lifts.
- **The executor reads 0% outside the `unit` tier.** `repo2ree-exec` runs
  *inside* the workbench container, where the host's coverage process cannot
  see it. Integration and e2e exercise it heavily; none of that is measured.
  Its real coverage comes from `executor/tests` in the `unit` tier.

Data layout is configured in `pyproject.toml`; one directory per tier rather
than one suffixed file per tier, because `coverage combine` treats sibling
`.coverage.*` files as its own parallel-mode output and consumes them.

## GUI Checks And Tests

Install dependencies:

```bash
npm --prefix gui ci
```

Run GUI checks:

```bash
make gui-checks
```

Run GUI unit tests:

```bash
make gui-tests
```

`make gui-checks` runs TypeScript for the app and e2e configs, Biome, knip, and
dependency-cruiser.

## End-To-End Tests

The Playwright config is `gui/playwright.config.ts`. It starts the Vite dev
server on `127.0.0.1:4173` and points the GUI at
`http://localhost:8000`.

Run e2e tests through Make:

```bash
make e2e-tests
```

That target starts the backend on `127.0.0.1:8000`, waits for it to respond,
then runs the Playwright `e2e` project from `gui/`.

The reviewer side of the lifecycle is a separate project under
`gui/tests/e2e/review/` — a spec per review step, each reproducing that
step in an isolated namespace and comparing the result with the author's
recorded evidence, plus `bundled.spec.ts` for the second evidence basis: an REE
that carries its own source and runtime, reviewed without reaching for an
origin:

```bash
make e2e-review
```

It stays out of `e2e-tests`: every spec provisions a real workbench, so the two
suites cost real time and are worth running independently. `push-gate` runs both.

Run the narrated demo flow:

```bash
make e2e-demo
```

Every browser project can also drive the image-backed stack instead of the dev
servers — `make e2e-tests-stack` / `make e2e-review-stack` /
`make e2e-demo-stack` do the whole flow in one command: build the local images,
`make stack-up` (compose control plane + agent container, via
`scripts/image-stack.sh`), run the playwright project, `make stack-clean`. With a
stack already up, `make e2e-tests-images` / `make e2e-review-images` /
`make e2e-demo-images` run just the playwright part. Playwright is pointed at the Caddy-served GUI (via `E2E_BASE_URL`,
which also skips the Vite dev server), so the GUI image's `/api` reverse
proxy and the backend/agent images are what get exercised. The stack is
addressed as `localhost` from the host or via compose service DNS from the
devcontainer; `scripts/image-stack.sh` picks automatically.

Those one-command flows own the whole lifecycle, so they end on `stack-clean`
(`image-stack.sh down --volumes`): the compose volumes go with the containers,
and so do any workbench containers and per-REE volumes the specs left on the
daemon. A stack you started yourself with `make stack-up` ends with
`make stack-down` instead, which keeps the volumes so the backend state and the
agent's identity survive to the next run — use `make stack-clean` when you want
that state gone too. The source-run `e2e-*` targets prune workbench leftovers on
exit for the same reason: their backend state is throwaway, so any REE the specs
did not delete is already unreachable. `make workbench-clean` does that prune on
its own, after an interrupted run.

The prune also sweeps unreferenced anonymous volumes — the hex-named ones the
bench image declares for itself (`docker:dind` declares `/var/lib/docker` and
`/certs`), which no name can address once their container is gone. The agent
now removes containers with `docker rm -v` so they no longer accumulate; the
sweep is what reclaims the ones from earlier runs.

The `repo2ree-store-{hash}` volumes are the exception: no cleanup touches them
by default. Each holds the executor/tools closure every bench mounts (~450MB),
keyed by bundle content — so rebuilding the executor or the tools bundle mints a
new one and orphans the old, which nothing will mount again. That makes them a
cache needing eviction, not state to preserve. `make store-gc` drops the ones no
container references and no build has recreated in `STORE_GC_DAYS` (14),
protecting the bundle this checkout resolves to so the next run still starts
warm; `make workbench-clean STORE=1` drops all of them, live one included, at
the cost of one full store copy per bundle on the next provision. Neither runs
as part of an e2e teardown — a test target should not silently evict a cache the
next run needs.

The `*-stack-published` variants validate the pushed images instead of local
builds (docker pulls the refs, nothing is built). They default to the Docker
Hub images the push targets publish; override `DOCKERHUB_NAMESPACE` /
`IMAGE_TAG` as with those targets. `make e2e-tests-stack-published
IMAGE_TAG=<tag>` is the full-suite gate for a pushed build.

The source-run `e2e-tests` remains the iteration loop (fast, easy to debug,
coverage-capable); the image-backed variants are the deployment gate before
pushing or promoting images.

`make commit-gate` is the fast pre-commit companion: static checks plus every
test tier that needs no docker, nix builds, or browsers (GUI unit,
backend unit, core integration). It takes well under a minute warm — that's
the point; commits should stay cheap. The exhaustive counterpart is the push
gate below.

The pre-commit hook does not run the gate — it checks that you did. On a green
run the gate records the tree it validated under `.validation-certificates/`,
whose own `.gitignore` keeps every certificate out of the repository while
keeping the directory in it. That ignore rule is load-bearing rather than
tidiness: a certificate is a hash of the working tree and lives inside it, so a
tracked one would change the thing it measures. `commit-gate-stamp.sh` refuses
to write a certificate git would track, so editing the rule away fails loudly
instead of rejecting every commit for no visible reason.

The hook (`.pre-commit-config.yaml`) compares that certificate against the tree
you are about to commit. The comparison is a hash, so it costs milliseconds, and
any edit to any staged file changes the hash: a certificate can be stale, never
wrong.

The split exists because pre-commit captures hook output rather than streaming
it. Running the gate from the hook meant a `git commit` that showed nothing for
the better part of a minute, which is how a `--no-verify` habit starts. Run the
gate in your own terminal, where you can watch it, and let the hook do the
bookkeeping.

The practical consequence is that the gate must see what you intend to commit:
it fingerprints the working tree, and the hook fingerprints the index. Stage
first, then run the gate, then commit. Partial staging (`git add -p`, or
committing a subset of a dirty tree) will not match, because the gate never
inspected that combination — re-run it against the content you actually mean to
ship, or use `git commit --no-verify` if you know you are committing something
the gate has not seen.

What the certificate cannot see is the toolchain: a gate that passed under a
different ruff than you have installed still produces a valid certificate. The
pin in `pyproject.toml` is what keeps that honest.

```bash
scripts/commit-gate-stamp.sh verify   # what the hook runs
```

`make push-gate` bundles the whole pre-publish sequence: it refuses a dirty
tree (pushed images must correspond to a commit), then runs the static
checks, builds the executor/tools bundles so the docker-gated test tiers
don't skip, runs the unit/integration suites, the source-run e2e suite, and
finally `e2e-tests-stack`. When it passes, the `:local` images it built are
exactly what the push targets will publish.

Run e2e coverage:

```bash
make coverage-e2e
```

This starts the backend *and* every agent under coverage — an e2e run is the
heaviest exercise the agent package gets (docker runtime, control link,
injection, chunked transfers), so measuring only the server reported that work
as uncovered.

E2E tests provision real workbench containers — the most expensive part of
any e2e test (bench start, nested dockerd boot, and a cold-cache DinD build
for anything that builds). The golden path therefore lives in one journey
spec, `tests/e2e/ree-pipeline.spec.ts`: a single run from provisioning
through seal and release, with each pipeline page asserted as a named
`test.step`, so the suite pays for one workbench and one runtime build.
Separate specs exist only for branches off that path (e.g. the origin-URL
source fetch). The shared e2e fixture attempts to release the workbench
after each test, including failures.

## Artifacts And Logs

All generated test artifacts should stay under `test-artifacts/`, and that
directory must stay safe to delete: nothing under it may be an input a suite
needs or a nix GC root. The executor/tools bundles are the counter-example that
motivated the rule — they live under `dist/bundles/` (see `mk/e2e.mk`) because
`nix build -o` makes them GC roots holding their store closures alive, and
because the suites *consume* them rather than produce them.

Useful locations:

| Path | Contents |
|---|---|
| `test-artifacts/api-server.log` | Backend log for plain e2e runs. |
| `test-artifacts/coverage/e2e/backend.log` | Backend log for e2e coverage runs. |
| `test-artifacts/coverage/` | Backend and e2e coverage reports. |
| `test-artifacts/property-based-tests/` | Hypothesis home: `<package>/` example databases plus its own caches. |
| `gui/test-artifacts/playwright/` | Playwright traces, screenshots, and videos. |
| `test-artifacts/traces/api-integration/` | API integration trace files and workbench log snapshots. |
| `dist/bundles/{exec,tools}` | Executor/tools bundles the agent injects — a build input, not an artifact. |

When a Docker-gated test fails, inspect both the workbench entrypoint log and
the nested daemon log:

```bash
docker logs repo2ree-wb-{ree_id}
docker exec repo2ree-wb-{ree_id} cat /var/log/dockerd.log
```

## Direct Commands

Direct commands are useful while debugging one tier:

```bash
pytest core/tests/unit
pytest core/tests/integration
pytest api/tests/unit
pytest api/tests/integration
pytest supervisor/tests/integration
pytest executor/tests
```

For one Playwright spec:

```bash
cd gui
npm exec -- playwright test -c playwright.config.ts --project=e2e tests/e2e/source.spec.ts
```
