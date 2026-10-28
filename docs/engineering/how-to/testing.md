# How to test repo2ree

> Status: current test layout (2026-07). Container-free checks run separately
> from Docker-gated integration and end-to-end flows.

## Quick map

| Target | What it runs |
|---|---|
| `just check-gui` | GUI TypeScript, Biome, knip, dependency-cruiser. |
| `just test-gui` | GUI Vitest tests — the `node` tier, measured (V8) into `coverage/node/unit/`. |
| `just test-gui-accessibility` | WCAG 2.2 AA, axe best-practice, and focused contrast checks over deterministic, browser-rendered application pages. |
| `just test-gui-screenshots` | Page-level screenshot regression suite with a real GUI and deterministic mocked API. |
| `just check-backend` | Ruff, Ruff format, and mypy across Python workspace packages. |
| `just check-scripts` | ShellCheck over every `scripts/**/*.sh`, plus Ruff and mypy over the Python tools. |
| `just test-backend-unit` | The container-free backend `unit` tier, measured into its data directory. |
| `just test-backend-integration` | The backend `integration` tier, measured. Builds the bundles first; Docker-gated tests skip when Docker is absent. |
| `just test-backend` | Both backend tiers, combined into one backend coverage report. |
| `just test-core-unit` / `test-api-unit` / … | One package's suite and isolated coverage contribution — the debugging loop. |
| `just test-e2e-gui` | Browser regression suite against a live API and GUI dev server. Measured. |
| `just test-e2e-review` | Browser regression suite, reviewer side: the reproduction specs. Measured. |
| `just demo-gui` | Narrated browser walkthrough with video. Measured. |
| `just demo-api` | The same stack driven over HTTP with no browser; records a `.cast` + transcript. Measured (Python only). |
| `just demo-gui-code-ocean` | Long-running external-capsule demo. Measured. |
| `just test-stack-existing <suite>` | Run any browser project or `demo-api` against an already-running image-backed stack. |
| `just test-stack-local <suite> [locations]` | Build local images, start an owned stack, run the suite, and clean it up. |
| `just test-stack-published <suite> [locations] [repository] [tag]` | Run the same flow against published registry images. |
| `just stack-up` / `stack-down` | Start/stop the image-backed stack, keeping its volumes (`testbed/src/repo2ree_testbed/stack/images.py`). |
| `just stack-clean` | Stop it and drop every volume it created, workbench leftovers included. |
| `just clean-workbenches` | Just the workbench leftovers; pass `1` to also drop every bundle store volume. |
| `just gc-bundle-store` | Remove every unused bundle store cache but the live one; pass a number to keep that many more. |
| `just gate-e2e-on [machine] [jobs]` | The assurance gate on a machine (`local`, or one of your own), its receipt and runs brought back here. |
| `just test-e2e-on <machine> <recipe> [args]` | Any e2e recipe on a machine, its per-test runs brought back here. |
| `just list-e2e-machines` / `just remove-e2e-machine <machine>` | List the machines; take one's dev container down and delete its clone. |
| `just cancel-e2e-on <machine>` | Stop the job running on a machine, as Ctrl-C on its run would. |
| `just commit-gate` | Fast pre-commit gate: documentation, static checks, and unit tests. Writes a receipt for the tree it passed on; the pre-commit hook checks that receipt. |
| `just check-doc-links-external` | Manually check external documentation URLs with retries and a local response cache; intentionally excluded from deterministic gates. |
| `just publish-gate` | The pre-publish gate: clean tree, all checks and tests, e2e source-run and image-backed. |
| `just render-backend-coverage <tier>` | Render a tier's HTML from data already on disk. |
| `just combine-backend-coverage` | Union of whichever backend tiers have been measured on this checkout. |
| `just attribute-backend-coverage` | Per-test coverage attribution over the two pytest tiers. |

## Before Docker-Gated Tests

Build the executor/tools bundles the provider injects into each workbench:

```bash
just build-e2e-bundles
```

The Docker-gated tiers skip when Docker or the bundles are absent. They do
not fake the workbench path; the first run pulls the pinned `docker:dind`
image.

## Backend Checks

Run all Python static checks:

```bash
just check-backend
```

Per-package targets are available:

```bash
just check-protocol
just check-core
just check-supervisor
just check-api
just check-executor
just check-docker-support
just check-provider
just check-workbench
```

These targets run `ruff check`, `ruff format`, and `mypy` for their package.
They may modify formatting.

## Backend Tests

Fast, container-free tests:

```bash
just test-backend-unit
```

Full backend test suite and combined unit/integration coverage report:

```bash
just test-backend
```

Per-package test targets:

```bash
just test-core
just test-api
just test-supervisor
just test-executor
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
just test-api-unit
just test-api-integration
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

**The tier, the Just recipe, and (for stack suites) the Playwright project are
one name.** A report therefore cannot be labelled with a suite that did not
produce it.

| Tier | Target | What it measures | Needs |
|---|---|---|---|
| `unit` | `just test-backend-unit` | Container-free single-component suites | nothing |
| `integration` | `just test-backend-integration` | Flows spanning components; mostly docker-gated | docker + bundles |
| `e2e-gui` | `just test-e2e-gui` | The live stack, browser-driven, author side | docker + browsers |
| `e2e-gui-review` | `just test-e2e-review` | The live stack, browser-driven, reviewer side | docker + browsers |
| `demo-gui` | `just demo-gui` | The narrated walkthrough stack | docker + browsers |
| `demo-gui-code-ocean` | `just demo-gui-code-ocean` | The external-capsule demo | docker + browsers + capsule |
| `demo-api` | `just demo-api` | The live stack over HTTP, no browser | docker |
| `node` | `just test-gui` | The GUI's Vitest suite: pure logic and components | nothing |

Suites are named `<purpose>-<interface>`: `e2e-` is a regression suite, `demo-` a
demonstration, `-gui` is browser-driven, `-api` drives the same stack over HTTP.
Every stack suite measures the same thing — the backend — whichever interface
drove it; see "The browser is not measured" below.

Branch coverage adds roughly 30% to pytest runtime. Per-package targets such as
`just test-core-unit` serve as the debugging loop and write isolated coverage
parts, but only the aggregate target combines every required part into the
tier's reportable data. A partial run therefore cannot be mistaken for a
complete tier.

A tier run produces *data*, not HTML. Render it when you want to look:

```bash
just test-backend-unit               # run + measure
just render-backend-coverage unit    # render, from data already on disk
```

Pass `COV_REPORT=term-missing` to a tier target for a terminal report during the
run itself, when you are actively closing gaps.

Three details matter when reading coverage:

- **`integration` is not defined by docker**, even though the target requires it.
  `core/tests/integration` spans components without containers, so it sits in
  this tier and pays for the `build-e2e-bundles` prerequisite without using it. The
  axis is scope; docker is what most flows of that scope happen to need. (That
  prerequisite is why `just test-backend-integration` triggers a nix build: the tier
  must not run against bundles from an older tree.)
- **The image-backed variants are unmeasured, permanently.** `test-stack-existing`,
  `test-stack-local` and `test-stack-published` run the backend and workbenches *inside
  containers*, beyond the host coverage process. Source-run suites produce the
  numbers; image-backed suites prove the production topology works without
  coverage instrumentation.
- **`combined` is rarely everything, and says so.** `just combine-backend-coverage`
  prints included and missing tiers. A full `publish-gate` measures
  `unit`, `integration`, `e2e-gui` and `e2e-gui-review`; the demo tiers are
  absent because gates do not run demos.

The report targets carry the runtime, like the rest of the Justfile:
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

Vite's dev-server sourcemaps identify a source by **basename alone** — `Workbench.ts`,
not `src/core/workbench/Workbench.ts`. The GUI has 7 ambiguous basenames covering 18
files, and a single e2e test loads all five distinct `index.ts` modules; their
coverage was being merged into one entry with line numbers from different files
landing on top of each other. Nothing reported a problem.

UI coverage belongs in the `node` tier instead, where Vitest transforms the files
itself and records their real paths (`SF:src/core/workbench/Workbench.ts`). That is also
the better instrument for the question: coverage asks "does this code have a test
exercising it", and a component test answers that directly, in seconds, where an
e2e run only shows a line executed while a workbench was being provisioned.

The Playwright suites keep their job — proving the pipeline works end to end, and
recording the demos — and keep measuring the **backend**, which is unaffected.

### The GUI reads low in `node`

`just test-gui` reports low coverage because the React shell has few component
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
   workbench        70%
   TOTAL        88%
```

These are filters over the tier's own data, not separate runs — so they cost no
extra test time and exist for every tier, including the stack tiers, which are
a single stack run and could never be decomposed by suite. They answer "how
well covered is this package", with every suite in the tier contributing.

Comparing one package across tiers is often the useful read: `workbench` is 70% in
`unit` and 87% in `combined`, because its docker runtime only runs under the
stack tiers.

Tier definitions live in `just/backend-tests.just`; package breakdown and shared
report rendering live in `testbed/src/repo2ree_testbed/python_coverage.py`. To re-render a
tier from data already measured, without repeating its suite:

```bash
just render-backend-coverage unit
```

Union of whatever has been measured:

```bash
just combine-backend-coverage
```

It skips tiers that were never run, so it is useful after any subset, and it
prints its own scope so you never have to guess what a "combined" number covers:

```
>> combined: unit integration e2e-gui e2e-gui-review
>> NOT included (never measured on this tree): demo-gui demo-api demo-gui-code-ocean
```

That is what a full `publish-gate` leaves behind. The demo tiers are absent because
no gate runs a demo — demos are demonstrations, and putting one on the publish
path would buy a number at the cost of a slower gate and a video nobody watches.
Measure them yourself when you want them in the union. `--keep` means combining
never destroys the per-tier data, so any tier report can be rebuilt without
re-running its suite.

Per-test attribution (which test hit which line) over the two pytest tiers:

```bash
just attribute-backend-coverage
```

Two things to know when reading a report:

- **The `unit` tier is a floor, not the truth.** The docker-gated transport
  (supervisor manager, hbom profilers, the provider's docker lifecycle) is not
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
just check-gui
```

Run GUI unit tests:

```bash
just test-gui
```

`just check-gui` runs TypeScript for the app and e2e configs, Biome, knip, and
dependency-cruiser.

## End-to-end tests

The Playwright config is `gui/playwright.config.ts`. It starts the Vite dev
server on `127.0.0.1:4173` and points the GUI at
`http://localhost:8000`.

Run E2E tests through Just:

```bash
just test-e2e-gui
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
just test-e2e-review
```

It stays out of `e2e-gui`: every spec provisions a real workbench, so the two
suites cost real time and are worth running independently. `publish-gate` runs both.

Run the narrated demo flow:

```bash
just demo-gui
```

Every browser project can also drive the image-backed stack instead of the dev
servers. Pass the Playwright project name to `test-stack-local`,
`test-stack-published`, or `test-stack-existing`; `demo-api` selects the HTTP
walkthrough instead. The local form builds images and owns stack startup and
cleanup, the published form owns a stack using registry images, and the existing
form only runs the suite. `E2E_BASE_URL` points Playwright to the Caddy-served GUI
and skips the Vite server, exercising the GUI proxy and all three images.

The host reaches the stack through `localhost`; the devcontainer uses Compose
service DNS. `testbed/src/repo2ree_testbed/stack/images.py` selects the correct address.

One-command flows end with `stack-clean`, which removes Compose volumes,
leftover workbenches, and per-REE volumes. For a manually started stack, use
`stack-down` to preserve backend state and workbench identity, or `stack-clean` to
remove them. Source-run `e2e-*` targets also prune unreachable workbenches.
After an interrupted run, invoke `just clean-workbenches` directly.

The prune also sweeps unreferenced anonymous volumes — the hex-named ones the
bench image declares for itself (`docker:dind` declares `/var/lib/docker` and
`/certs`), which no name can address once their container is gone. The workbench
now removes containers with `docker rm -v` so they no longer accumulate; the
sweep is what reclaims the ones from earlier runs.

Cleanup preserves `repo2ree-store-{hash}` volumes because each is a reusable
executor/tools cache of about 600 MB. A bundle change creates a new volume and
leaves the old one unused.

The prune at the start of every e2e run keeps the current checkout's cache and
the two newest unused ones, and removes the rest; `just prune-test-artifacts
--keep-stores N` keeps a different number. `just gc-bundle-store` removes every
unused cache but the current checkout's, and `just clean-workbenches 1` removes
every cache, including the current one.

Providers that share a Docker daemon also share the cache: the first to need a
bundle copies it into the volume while the others wait on a lock held on the
daemon, so stacks running side by side never copy into the same volume at
once.

`test-stack-published` validates pushed images instead of local builds
(Docker pulls the refs; nothing is built). For an ad hoc run they default to the
Docker Hub images at `IMAGE_TAG`. The promotion workflow uses
`just validate-candidate`, which resolves the candidate across every
registry and supplies explicit per-component `@sha256` references to both
published-stack GUI projects. That digest-bound run, rather than a mutable tag
run, is what can produce an edge-promotion receipt.

The source-run `e2e-gui` remains the iteration loop (fast, easy to debug,
coverage-capable); the image-backed variants are the deployment gate before
pushing or promoting images.

`just commit-gate` runs offline docs and static checks plus the unit tests. It
takes about a minute when warm and leaves fresh `unit` and `node` coverage. Use
the push gate for the integration and end-to-end suites.

The pre-commit hook checks that you ran the gate. A successful gate writes a
receipt naming the tree hash, `.receipts/commit-gate.json`; every gate writes its
receipt there in the same form (`scripts/gates/receipts.py`). The directory's
`.gitignore` keeps receipts untracked because tracking one would change the tree
it measures, and the gates refuse to write a receipt Git would track.

The hook (`.pre-commit-config.yaml`) compares that receipt against the tree
you are about to commit. The comparison is a hash, so it costs milliseconds, and
any edit to any staged file changes the hash: a receipt can be stale, never
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

What the receipt cannot see is the toolchain: a gate that passed under a
different ruff than you have installed still produces a valid receipt. The
pin in `pyproject.toml` is what keeps that honest.

```bash
python -m scripts.gates.commit_gate verify   # what the hook runs
```

`just publish-gate` bundles the whole pre-publish sequence: it refuses a dirty
tree (pushed images must correspond to a commit), then runs the static
checks, builds the executor/tools bundles so the docker-gated test tiers
don't skip, runs the unit/integration suites, the source-run e2e suite, and
finally runs both browser projects against local images. When it passes, the `:local` images it built are
exactly what the push targets will publish.

Every source-run stack suite is measured — `just test-e2e-gui` is the coverage run.
This starts the backend *and* every compute-side process under coverage — an
e2e run is the heaviest exercise those packages get (docker lifecycle, control
link, injection, chunked transfers), so measuring only the server reported that
work as uncovered.

End-to-end tests provision real workbenches. Starting a workbench, booting its
nested daemon, and building against a cold cache dominate test time. The golden
path therefore uses one journey spec, `tests/e2e/ree-pipeline.spec.ts`, from
provisioning through seal and release. Named `test.step` blocks identify each
stage without repeating setup.

Separate specs cover only branches such as origin-URL source fetch. The shared
fixture attempts to release the workbench after every test, including failures.

## Running on another machine

The e2e tiers can run on a machine other than this one: a VM, a bigger
workstation, a CI host. Such a machine runs the stacks itself, because a bench
calls its API back through `host.docker.internal`, so the API, its providers,
and Docker must share a host. `local` is always one; others are listed in
`.config/machines.toml` in your checkout (or the file `$REPO2REE_MACHINES` names).
Git ignores `.config/`, since hosts are your own, and the file survives a
rebuilt dev container because the checkout does:

```toml
[machines.vm]
host = "repo2ree@vm" # an ssh destination: an alias from ~/.ssh/config, or user@host
jobs = 6             # stacks side by side per tier
# shell = [...]      # what every command runs inside; by default the clone's .envrc, via direnv
# fetch = "slim"     # or "full"; slim leaves runtime tarballs and REE archives there
# container = "repo2ree-dev"  # the Compose project of the dev container there
```

A machine works as your own computer does: a clone, `~/repo2ree` of its SSH user,
and the dev container brought up from it with Compose, mounting it at `/repo2ree`,
the path of your own checkout in the dev container. It needs Git and a Docker Engine
with Compose that its SSH user may use. Compose reads `docker-compose.dev.yml`, as
here, with `docker/dev/machine.compose.yml` over it, which builds the Nix dev image
(`docker/dev/nix.Dockerfile`) and keeps the container up for runs. Compose rebuilds
the image when its inputs change and otherwise keeps the container, so the bundles
and caches in it carry over. The container gives its user the IDs of the clone's
owner, so what it writes there is the SSH user's. Compose gives it a network of its
own: benches join it and reach the API inside the container by its name. `just
remove-e2e-machine vm` cleans up the stacks and workbenches runs left, takes the
container down, and deletes the clone.

For a VM you reach with an admin login, `tools/ssh/setup-vm.sh <admin login>`, run
on your own computer, makes a key for it, loads it into your SSH agent, and
creates a `repo2ree` user there in the docker group that accepts the key; the dev
container uses the key through the agent VS Code forwards. It also copies the VM host key
into `.config/known_hosts` and names the VM in `.config/machines.toml` as
the machine `vm` (`--name` picks another), so `just gate-e2e-on vm` works from
then on. Runs check host keys against that file and your own
`~/.ssh/known_hosts`, and refuse a host they do not know rather than ask.
`--revoke` takes it all away again.

`just gate-e2e-on vm` pushes HEAD to the clone there, checks it out clean, brings
the dev container up, runs `just assurance-gate` in it, and brings back every run it
made and, if it passed, its receipt. A receipt binds a tree, not a machine, so it
holds here as it held there; the recipe ends by checking that. `just test-e2e-on vm
test-e2e-system` runs a single tier the same way. Only a commit can be shipped, so
both refuse a working tree with changes. The first run on a machine, and the first
after the dev image's inputs change, builds the image there.

On another machine the recipe runs as a job detached from SSH, so a dropped
connection does not end it. The run shows the job's log as it grows; when the
connection drops it says so and reconnects, continuing where the log left off,
for up to 30 minutes. After that, or once your computer was asleep or the run
killed, run the same command again at the same commit: it picks the job back up,
or brings back its results if it has ended, instead of starting it anew. A job's
command, log, and exit code are in `test-artifacts/machine-job/` of the clone
there.

One job runs on a machine at a time. A different command and `just
remove-e2e-machine` refuse while one runs and name it. Ctrl-C on a run cancels its job there, as it would here; `just cancel-e2e-on
vm` does the same from anywhere.

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
| `test-artifacts/e2e/<tier>-<timestamp>/` | One e2e run: `run.json`, an `index.html`, and `tests/<test>/` per test (a whole-suite tier such as `demo-gui` has one entry, `tests/suite/`) with `test.json`, `junit.xml`, `logs/`, the behaviour `dossier/`, its `verification/` and `traces/`, and what the client kept in `artifacts/`. |
| `test-artifacts/python/coverage/` | Backend coverage data and HTML, one report per tier, plus per-test attribution under `context/`. |
| `test-artifacts/python/sessions/`, `tests/`, `services/` | pytest sessions, per-test output, and service logs of the pytest tiers. |
| `test-artifacts/node/coverage/unit/` | GUI Vitest coverage (V8), from `just test-gui`. |
| `test-artifacts/browser/tests/<project>/` | Playwright output of the browser suites that run without a stack (accessibility, screenshots). |
| `test-artifacts/assurance/` | Output of the assurance packages' tests, and `inspect-dossier` reports of dossiers collected outside an e2e run. |
| `test-artifacts/cache/hypothesis/` | Hypothesis home: `<package>/` example databases plus its own caches. |
| `test-artifacts/fixtures/` | Archives the suites pack on demand from `examples/`; repacked every run. |
| `test-artifacts/state/` | Throwaway state of test stacks (control planes, providers, workbenches). State, not output, but safe to delete. |
| `dist/bundles/{exec,tools}` | Executor/tools bundles the workbench injects: a build input, not an artifact. |

Views of the repository (diagrams, metrics, the overview) live under `reports/`, not here;
a report that shows test output copies what it shows (see `just repo-overview`).

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
