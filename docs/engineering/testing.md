# repo2ree - Engineering Test Guide

> Status: current test layout (2026-07). The suite intentionally separates
> container-free checks from Docker-gated integration and e2e flows.

## Quick Map

| Target | What it runs |
|---|---|
| `make gui-checks` | GUI TypeScript, Biome, knip, dependency-cruiser. |
| `make gui-tests` | GUI Vitest tests — the `node` tier, measured (V8) into `coverage/node/unit/`. |
| `make be-checks` | Ruff, Ruff format, and mypy across Python workspace packages. |
| `make scripts-checks` | ShellCheck over `scripts/*.sh`. |
| `make be-unit-tests` | The container-free backend `unit` tier, measured into its data directory. |
| `make be-integration-tests` | The backend `integration` tier, measured. Builds the bundles first; Docker-gated tests skip when Docker is absent. |
| `make be-tests` | Both backend tiers. |
| `make core-unit-tests` / `api-unit-tests` / … | One package's suite, unmeasured — the debugging loop. |
| `make e2e-gui` | Browser regression suite against a live API and GUI dev server. Measured. |
| `make e2e-gui-review` | Browser regression suite, reviewer side: the reproduction specs. Measured. |
| `make demo-gui` | Narrated browser walkthrough with video. Measured. |
| `make demo-api` | The same stack driven over HTTP with no browser; records a `.cast` + transcript. Measured (Python only). |
| `make demo-gui-code-ocean` | Long-running external-capsule demo. Measured. |
| `make e2e-gui-on-stack` / `e2e-gui-review-on-stack` / `demo-gui-on-stack` | Suite / review / demo against an already-running image-backed stack. |
| `make e2e-gui-stack-local` / `e2e-gui-review-stack-local` / `demo-gui-stack-local` | One command: build local images, `stack-up`, run the project, `stack-clean`. |
| `make e2e-gui-stack-published` / `e2e-gui-review-stack-published` / `demo-gui-stack-published` | The same flows against the pushed registry images (nothing built). |
| `make stack-up` / `stack-down` | Start/stop the image-backed stack, keeping its volumes (`scripts/image-stack.sh`). |
| `make stack-clean` | Stop it and drop every volume it created, workbench leftovers included. |
| `make workbench-clean` | Just the workbench leftovers; `STORE=1` also drops every bundle store volume. |
| `make store-gc` | Evict bundle store caches unused for `STORE_GC_DAYS` (14), keeping the live one. |
| `make commit-gate` | Fast pre-commit gate: static checks + all container-free test tiers. Certifies the tree it passed on; the pre-commit hook checks that certificate. |
| `make push-gate` | The pre-publish gate: clean tree, all checks and tests, e2e source-run and image-backed. |
| `make be-coverage-report TIER=<tier>` | Render a tier's HTML from data already on disk. |
| `make be-coverage-combined` | Union of whichever backend tiers have been measured on this checkout. |
| `make be-coverage-context` | Per-test coverage attribution over the two pytest tiers. |

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
make agent-checks
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

Coverage is measured per **tier**, one report each. Two rules do most of the
work here:

**Running a tier measures it.** No separate "coverage" target exists to
remember, so the suites a tier runs and the suites it measures cannot drift
apart.

**The tier, the make target, and (for stack suites) the Playwright project are
one name.** A report therefore cannot be labelled with a suite that did not
produce it.

| Tier | Target | What it measures | Needs |
|---|---|---|---|
| `unit` | `make be-unit-tests` | Container-free single-component suites | nothing |
| `integration` | `make be-integration-tests` | Flows spanning components; mostly docker-gated | docker + bundles |
| `e2e-gui` | `make e2e-gui` | The live stack, browser-driven, author side | docker + browsers |
| `e2e-gui-review` | `make e2e-gui-review` | The live stack, browser-driven, reviewer side | docker + browsers |
| `demo-gui` | `make demo-gui` | The narrated walkthrough stack | docker + browsers |
| `demo-gui-code-ocean` | `make demo-gui-code-ocean` | The external-capsule demo | docker + browsers + capsule |
| `demo-api` | `make demo-api` | The live stack over HTTP, no browser | docker |
| `node` | `make gui-tests` | The GUI's Vitest suite: pure logic and components | nothing |

Suites are named `<purpose>-<interface>`: `e2e-` is a regression suite, `demo-` a
demonstration, `-gui` is browser-driven, `-api` drives the same stack over HTTP.
Every stack suite measures the same thing — the backend — whichever interface
drove it; see "The browser is not measured" below.

Measuring costs roughly 30% wall clock on the pytest tiers (branch coverage is
on). That is the price of the guarantee above, and it is why the **per-package**
targets — `make core-unit-tests`, `make api-integration-tests`, and friends —
stay unmeasured. They are the debugging loop, and a partial run writing a tier's
data directory would make that tier's number mean "core, plus whatever else
someone happened to run today", which is exactly the blend the tier split exists
to prevent.

A tier run produces *data*, not HTML. Render it when you want to look:

```bash
make be-unit-tests                   # run + measure
make be-coverage-report TIER=unit    # render, from data already on disk
```

Pass `COV_REPORT=term-missing` to a tier target for a terminal report during the
run itself, when you are actively closing gaps.

Three things the table does not say, all worth knowing before reading a number:

- **`integration` is not defined by docker**, even though the target requires it.
  `core/tests/integration` spans components without containers, so it sits in
  this tier and pays for the `e2e-bundles` prerequisite without using it. The
  axis is scope; docker is what most flows of that scope happen to need. (That
  prerequisite is why `make be-integration-tests` triggers a nix build: the tier
  must not run against bundles from an older tree.)
- **The image-backed variants are unmeasured, permanently.** `-on-stack`,
  `-stack-local` and `-stack-published` run the backend and agents *inside
  containers*, where the host's coverage process cannot see them. That is a
  division of labour rather than a gap: the measured source-run path produces the
  numbers, and the image-backed path — which `push-gate` runs — proves the
  un-instrumented topology works.
- **`combined` is rarely everything, and says so.** `make be-coverage-combined`
  prints the tiers it included *and* the ones it did not, because a number
  labelled "combined" otherwise reads as complete. A full `push-gate` measures
  `unit`, `integration`, `e2e-gui` and `e2e-gui-review`; the demo tiers are
  absent because no gate runs a demo, deliberately.

The report targets carry the runtime, like the rest of the Makefile:
`be-coverage-*` reports on Python, `gui-coverage-*` on the GUI.

Each tier writes its data to `test-artifacts/coverage/python/data/<tier>/` and
its HTML report to `test-artifacts/coverage/python/<tier>/`, so a tier's number
always means "what this way of testing reaches" and never a blend of two.

### Runtime above tier

Under `test-artifacts/coverage/` the first level is the **measuring runtime**,
not the tier:

| Subtree | Tool | Covers |
|---|---|---|
| `coverage/python/` | coverage.py | the six uv workspace packages |
| `coverage/node/` | V8 via vitest | the GUI |

That order is what keeps `combined` meaningful. Combining tiers is a *coverage.py
operation* — `coverage combine`, over `.coverage` databases — with no
cross-language form: no algorithm unions a Python line count with a JavaScript
one, and the two share no denominator. Each runtime therefore owns a `combined/` inside
its own subtree, and there is deliberately **no** `coverage/combined/` above them.

Every python tier writes into `coverage/python/`; `node` is the GUI's only tier,
so it has nothing to union. An absent tier directory means "this way of testing
does not exercise that runtime", not "someone forgot to run it".

### The browser is not measured

The Playwright suites drive a real browser but record no JavaScript coverage.
They used to: a fixture captured V8 per test and monocart merged it into
`coverage/browser/<tier>/`. That was removed, because the numbers were wrong.

Vite's dev-server sourcemaps identify a source by **basename alone** — `Agent.ts`,
not `src/core/agent/Agent.ts`. The GUI has 7 ambiguous basenames covering 18
files, and a single e2e test loads all five distinct `index.ts` modules; their
coverage was being merged into one entry with line numbers from different files
landing on top of each other. Nothing reported a problem.

UI coverage belongs in the `node` tier instead, where Vitest transforms the files
itself and records their real paths (`SF:src/core/agent/Agent.ts`). That is also
the better instrument for the question: coverage asks "does this code have a test
exercising it", and a component test answers that directly, in seconds, where an
e2e run only shows a line executed while a workbench was being provisioned.

The Playwright suites keep their job — proving the pipeline works end to end, and
recording the demos — and keep measuring the **backend**, which is unaffected.

### The GUI reads low in `node`

`make gui-tests` reads low, and unlike the other low numbers here that one is
**a real gap, not a measurement artifact**. The React shell is only beginning to
be covered, and nothing else covers it either: the Playwright suites drive the
shell but record no JavaScript coverage, for the reasons above. Closing it means
writing more component tests, which land in this same tier and lift this same
number.

The figure itself is deliberately not written down here or in `vite.config.js`.
It moves on every run that adds a test, so a copy in prose is a copy that goes
stale; run the tier and read the report it prints.

Every file matching the config's `include` counts, whether a test imported it or
not. That is what makes the number honest rather than flattering: measure only
imported files and the same suite reads far higher — and *improves when you
delete a test*. Under the V8 provider `include` gives that behaviour on its own
and `all: true` measures as a no-op, but the flag stays because it names the
property the number depends on rather than trusting a provider default.

### The `node` tier has two projects

The tier is one Vitest run with one coverage report, split into two projects by
file extension:

| Project | Files | Environment |
|---|---|---|
| `logic` | `src/**/*.test.ts` | `node` |
| `component` | `src/**/*.test.tsx` | `jsdom`, plus `tests/componentSetup.ts` |

Component tests use React Testing Library and `@testing-library/user-event`, and
select by **role and accessible name** rather than by styled text — several
components (`RunActionButton`, `OutcomeBadge`) carry doc comments promising that
name, and the tests are what hold them to it.

The split is a cost and a correctness measure, not a preference. jsdom costs
~1.7s of environment setup per file, so switching it on globally took the suite
from 2.9s to 11s; it also broke `scriptTemplates/paths.test.ts`, which reads a
contract fixture off disk through `import.meta.url` and cannot resolve it once
that URL is `http://`. Projects split the *run*, not the measurement — `coverage`
stays at the config root and both projects report into it — so this remains one
tier with one number.

Run one side alone while iterating:

```bash
cd gui && npx vitest --project component
```

### By module

Every tier is also broken down by source package, into
`test-artifacts/coverage/python/<tier>/by-module/<package>/`, and each run prints the
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
extra test time and exist for every tier, including the stack tiers, which are
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
make be-coverage-report TIER=unit
```

Union of whatever has been measured:

```bash
make be-coverage-combined
```

It skips tiers that were never run, so it is useful after any subset, and it
prints its own scope so you never have to guess what a "combined" number covers:

```
>> combined: unit integration e2e-gui e2e-gui-review
>> NOT included (never measured on this tree): demo-gui demo-api demo-gui-code-ocean
```

That is what a full `push-gate` leaves behind. The demo tiers are absent because
no gate runs a demo — demos are demonstrations, and putting one on the publish
path would buy a number at the cost of a slower gate and a video nobody watches.
Measure them yourself when you want them in the union. `--keep` means combining
never destroys the per-tier data, so any tier report can be rebuilt without
re-running its suite.

Per-test attribution (which test hit which line) over the two pytest tiers:

```bash
make be-coverage-context
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
make e2e-gui
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
make e2e-gui-review
```

It stays out of `e2e-gui`: every spec provisions a real workbench, so the two
suites cost real time and are worth running independently. `push-gate` runs both.

Run the narrated demo flow:

```bash
make demo-gui
```

Every browser project can also drive the image-backed stack instead of the dev
servers. The suffix names **who provides the stack**:

| Suffix | Who provides the stack | Builds anything? |
|---|---|---|
| *(none)* | the target itself, from source — vite dev server + uvicorn | no |
| `-on-stack` | you did, with `make stack-up` — nothing is started or stopped | no |
| `-stack-local` | the target, from `:local` images it builds first | yes |
| `-stack-published` | the target, from the pushed registry images | no |

The `-stack-local` targets do the whole flow in one command: build the local images,
`make stack-up` (compose control plane + agent container, via
`scripts/image-stack.sh`), run the playwright project, `make stack-clean`. With a
stack already up, `make e2e-gui-on-stack` / `make e2e-gui-review-on-stack` /
`make demo-gui-on-stack` run just the playwright part. Playwright is pointed at the Caddy-served GUI (via `E2E_BASE_URL`,
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
`IMAGE_TAG` as with those targets. `make e2e-gui-stack-published
IMAGE_TAG=<tag>` is the full-suite gate for a pushed build.

The source-run `e2e-gui` remains the iteration loop (fast, easy to debug,
coverage-capable); the image-backed variants are the deployment gate before
pushing or promoting images.

`make commit-gate` is the fast pre-commit companion: static checks plus every
test tier that needs no docker, nix builds, or browsers (GUI unit, backend unit,
core integration). It runs in about a minute warm — commits should stay cheap,
and that budget is the constraint any change to the gate has to answer to. Two
of its three suites are tier targets, so a green gate also leaves fresh `unit`
and `node` coverage on disk; that costs roughly 13s of the minute, which is the
price of never having an unmeasured tier run. The exhaustive counterpart is the
push gate below.

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
finally `e2e-gui-stack-local`. When it passes, the `:local` images it built are
exactly what the push targets will publish.

Every source-run stack suite is measured — `make e2e-gui` is the coverage run.
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

All generated test artifacts stay under the single repo-root `test-artifacts/`
— the GUI suites included, which is why `gui/` has no artifact root of its own.
Paths are derived from the file that writes them (`gui/tests/artifacts.ts`
anchors on `__dirname`; the Playwright config resolves `outputDir` against its
own directory), never from `process.cwd()`, so they cannot drift with the
working directory a suite happens to be invoked from. That
directory must stay safe to delete: nothing under it may be an input a suite
needs or a nix GC root. The executor/tools bundles are the counter-example that
motivated the rule — they live under `dist/bundles/` (see `mk/e2e.mk`) because
`nix build -o` makes them GC roots holding their store closures alive, and
because the suites *consume* them rather than produce them.

Useful locations:

| Path | Contents |
|---|---|
| `test-artifacts/coverage/python/<tier>/` | Backend coverage, one report per tier, plus `combined/`. |
| `test-artifacts/coverage/python/context/` | Per-test attribution (`be-coverage-context`). A different *view* over the pytest tiers, not a fifth tier — it is never part of `combined`. |
| `test-artifacts/coverage/node/unit/` | GUI Vitest coverage (V8), from `make gui-tests`. |
| `test-artifacts/playwright/<suite>/` | Playwright traces, screenshots, and videos. |
| `test-artifacts/traces/<suite>/` | OpenTelemetry spans and workbench log snapshots. Keyed by *suite*, not by coverage tier: `api-unit/`, `api-integration/`, `api-real-server/`, `supervisor-e2e/`. |
| `test-artifacts/property-based-tests/` | Hypothesis home: `<package>/` example databases plus its own caches. |
| `test-artifacts/logs/` | `api-server.log` for plain runs, `backend-<tier>.log` and `agent-<tier>.log` for measured ones. |
| `test-artifacts/casts/` | The API walkthrough `.cast` recording and its markdown transcript. |
| `test-artifacts/fixtures/` | Archives the suites pack on demand from `examples/`; repacked every run. |
| `test-artifacts/state/agents/` | Throwaway e2e agent identities; with `--agents N`, agent *i* > 1 uses `agents-<i>/`. State, not output — but still safe to delete. |
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
npm exec -- playwright test -c playwright.config.ts --project=e2e-gui tests/e2e/source.spec.ts
```
