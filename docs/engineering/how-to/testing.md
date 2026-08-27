# How to test repo2ree

> Status: current test layout (2026-07). Container-free checks run separately
> from Docker-gated integration and end-to-end flows.

## Quick map

| Target | What it runs |
|---|---|
| `make gui-checks` | GUI TypeScript, Biome, knip, dependency-cruiser. |
| `make gui-tests` | GUI Vitest tests — the `node` tier, measured (V8) into `coverage/node/unit/`. |
| `make gui-accessibility-tests` | WCAG 2.2 AA, axe best-practice, and focused contrast checks over deterministic, browser-rendered application pages. |
| `make gui-screenshot-tests` | Page-level screenshot regression suite with a real GUI and deterministic mocked API. |
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
| `make commit-gate` | Fast pre-commit gate: documentation, static checks, and all container-free test tiers. Certifies the tree it passed on; the pre-commit hook checks that certificate. |
| `make docs-links-external` | Manually check external documentation URLs with retries and a local response cache; intentionally excluded from deterministic gates. |
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

Branch coverage adds roughly 30% to pytest runtime. Per-package targets such as
`make core-unit-tests` therefore stay unmeasured and serve as the debugging
loop. Allowing partial runs to write tier data would make a tier's result an
unreliable blend of whichever packages ran most recently.

A tier run produces *data*, not HTML. Render it when you want to look:

```bash
make be-unit-tests                   # run + measure
make be-coverage-report TIER=unit    # render, from data already on disk
```

Pass `COV_REPORT=term-missing` to a tier target for a terminal report during the
run itself, when you are actively closing gaps.

Three details matter when reading coverage:

- **`integration` is not defined by docker**, even though the target requires it.
  `core/tests/integration` spans components without containers, so it sits in
  this tier and pays for the `e2e-bundles` prerequisite without using it. The
  axis is scope; docker is what most flows of that scope happen to need. (That
  prerequisite is why `make be-integration-tests` triggers a nix build: the tier
  must not run against bundles from an older tree.)
- **The image-backed variants are unmeasured, permanently.** `-on-stack`,
  `-stack-local` and `-stack-published` run the backend and agents *inside
  containers*, beyond the host coverage process. Source-run suites produce the
  numbers; image-backed suites prove the production topology works without
  coverage instrumentation.
- **`combined` is rarely everything, and says so.** `make be-coverage-combined`
  prints included and missing tiers. A full `push-gate` measures
  `unit`, `integration`, `e2e-gui` and `e2e-gui-review`; the demo tiers are
  absent because gates do not run demos.

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

That order keeps `combined` meaningful. `coverage combine` merges Python
`.coverage` databases; it cannot combine Python and JavaScript line counts.
Each runtime therefore owns a `combined/` directory; no shared
`coverage/combined/` sits above them.

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

`make gui-tests` reports low coverage because the React shell has few component
tests. Playwright drives the shell but records no JavaScript coverage. Add
component tests to close this gap.

This page does not copy the changing percentage. Run the tier and read its
report.

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

jsdom adds about 1.7 seconds of setup per file. Enabling it globally increased
the suite from 2.9 to 11 seconds and broke a disk fixture that relies on
`import.meta.url`. Projects split the run, while root-level coverage combines
both projects into one tier.

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

All of this lives in `mk/be-tests.mk`: the tier definitions, the package list
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

## GUI checks and tests

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

## End-to-end tests

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

The `-stack-local` targets build local images, start the stack, run Playwright,
and clean up. With a stack already running, the `*-on-stack` targets run only
Playwright. `E2E_BASE_URL` points Playwright to the Caddy-served GUI and skips
the Vite server, exercising the GUI proxy and all three images.

The host reaches the stack through `localhost`; the devcontainer uses Compose
service DNS. `scripts/image-stack.sh` selects the correct address.

One-command flows end with `stack-clean`, which removes Compose volumes,
leftover workbenches, and per-REE volumes. For a manually started stack, use
`stack-down` to preserve backend state and agent identity, or `stack-clean` to
remove them. Source-run `e2e-*` targets also prune unreachable workbenches.
After an interrupted run, invoke `make workbench-clean` directly.

The prune also sweeps unreferenced anonymous volumes — the hex-named ones the
bench image declares for itself (`docker:dind` declares `/var/lib/docker` and
`/certs`), which no name can address once their container is gone. The agent
now removes containers with `docker rm -v` so they no longer accumulate; the
sweep is what reclaims the ones from earlier runs.

Cleanup preserves `repo2ree-store-{hash}` volumes because each is a reusable
executor/tools cache of about 450 MB. A bundle change creates a new volume and
leaves the old one unused.

`make store-gc` removes unreferenced caches older than `STORE_GC_DAYS` (14) but
keeps the bundle used by the current checkout. `make workbench-clean STORE=1`
removes every cache, including the current one. End-to-end teardown never
evicts these caches automatically.

The `*-stack-published` variants validate pushed images instead of local builds
(Docker pulls the refs; nothing is built). For an ad hoc run they default to the
Docker Hub images at `IMAGE_TAG`. The promotion workflow uses
`make validate-image-candidate`, which resolves the candidate across every
registry and supplies explicit per-component `@sha256` references to both
published-stack GUI projects. That digest-bound run, rather than a mutable tag
run, is what can produce an edge-promotion receipt.

The source-run `e2e-gui` remains the iteration loop (fast, easy to debug,
coverage-capable); the image-backed variants are the deployment gate before
pushing or promoting images.

`make commit-gate` runs offline docs and static checks plus all tests that need
no Docker, Nix build, or browser. It takes about a minute when warm and leaves
fresh `unit` and `node` coverage. Use the push gate for the exhaustive suite.

The pre-commit hook checks that you ran the gate. A successful gate records a
tree hash under `.validation-certificates/`. Its `.gitignore` keeps certificates
untracked because tracking a certificate would change the tree it measures.
`commit-gate-stamp.sh` refuses to write a certificate Git would track.

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

End-to-end tests provision real workbenches. Starting a workbench, booting its
nested daemon, and building against a cold cache dominate test time. The golden
path therefore uses one journey spec, `tests/e2e/ree-pipeline.spec.ts`, from
provisioning through seal and release. Named `test.step` blocks identify each
stage without repeating setup.

Separate specs cover only branches such as origin-URL source fetch. The shared
fixture attempts to release the workbench after every test, including failures.

## Artifacts and logs

All generated test output lives under the repository-level `test-artifacts/`.
Writers resolve paths from their own files, not `process.cwd()`, so invocation
location cannot change the destination.

The directory must remain safe to delete: it cannot contain suite inputs or Nix
GC roots. Executor and tools bundles therefore live under `dist/bundles/`; tests
consume them, and `nix build -o` keeps their store closures alive.

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

## Direct commands

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
