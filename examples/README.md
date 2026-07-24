# Examples

Shared example inputs. Everything here is read by more than one place — the
frontend e2e and demo suites, the API walkthrough, and by hand when trying the
app — so it lives at the repository root rather than inside one suite.

## `projects/`

Small source projects the suites author REEs from. They are ordinary source
trees: no REE metadata, no receipts. `python-hello-world.tar.gz` is the packed
form of `python_hello_world/`, uploaded as-is by the specs that exercise the
upload path.

## `rees/`

Complete REEs, packaged the way `ree-archive` downloads them — the shape the
app loads back (workbench step → "Load REE bundle", or `POST
/api/v1/rees/{id}/ree:load`).

### `ree-hello-world.zip`

The REE the Python hello-world demo authors
(`frontend/tests/demo/ree-create-python-hello-world.spec.ts`), carrying its real
author evidence: the frozen source snapshot, the four overlay scripts, the SBOM,
the reproducibility report, the captured experiment result, and the six author
receipts from that run.

Two deliberate differences from what the demo downloaded:

- **Unsealed.** The seal stamps are stripped, so loading it yields an editable
  REE rather than a read-only artifact.
- **No runtime artifact.** The demo's `runtime.tar` is a 327 MB Docker image
  export, too large to version, so it is dropped and the manifest records
  `runtime_included: false` with the runtime path pointing back at its workspace
  location. Loading the bundle and building the runtime reproduces it.

Its source was acquired by upload, so the manifest carries a `swhid` but no
origin URL. A source review of this REE therefore reports that the author
baseline has no independently acquirable origin — the honest verdict for an
upload-acquired source, and the reason a review fixture with a URL origin is
still worth adding.

## `code-ocean/`

Downloaded third-party capsules, fetched on demand and gitignored (they are
large and not ours to redistribute). See `docs/research/code-ocean.md`.
