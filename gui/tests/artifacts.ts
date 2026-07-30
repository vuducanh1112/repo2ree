/**
 * Where the GUI suites write their artifacts: the repo-wide
 * ``test-artifacts/`` root, not a second one under ``gui/``.
 *
 * Anchored to this file rather than to ``process.cwd()``. Every entry point
 * happens to run ``cd gui`` first today, which made a cwd-relative path
 * accidentally correct — and would have made it silently wrong (writing
 * somewhere else, not failing) the first time playwright ran from the repo root.
 * A path derived from the file can only break if the file moves, which is a
 * visible edit.
 *
 * ``__dirname``, not ``import.meta.dirname``: package.json declares no
 * ``"type"``, so Playwright's TypeScript transform emits CommonJS and
 * ``import.meta`` is unavailable here — a module using it fails at import. The
 * plain-node ``scripts/gen-coverage.mjs`` is real ESM and uses
 * ``import.meta.dirname`` instead; the two anchors cannot share a file.
 */

import { join } from "node:path";

/** Repo root — this file is gui/tests/, so two levels up. */
const REPO_ROOT = join(__dirname, "..", "..");

/** The one gitignored artifact root, shared with the Python suites. */
const ARTIFACTS_DIR = join(REPO_ROOT, "test-artifacts");

/**
 * Per-test raw V8 captures for one coverage tier, merged into a report by
 * ``scripts/gen-coverage.mjs``. Keyed by tier so a ``demo`` run cannot
 * overwrite what an ``e2e`` run measured.
 */
export function browserCoverageRawDir(tier: string): string {
  return join(ARTIFACTS_DIR, "coverage", "browser", "raw", tier);
}

/** Archives the suites pack on demand from the checked-in ``examples/`` tree. */
export const FIXTURES_DIR = join(ARTIFACTS_DIR, "fixtures");
