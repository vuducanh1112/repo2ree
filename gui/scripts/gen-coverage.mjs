// Merge the per-test browser V8 coverage captured by the e2e suite (written by
// the jsCoverage fixture when E2E_COVERAGE_TIER is set) into one istanbul/lcov +
// HTML report. Run after the Playwright e2e run; `make coverage-e2e` does both.
//
// V8 -> source mapping leans on the Vite dev server's sourcemaps, so this is
// meaningful only against the dev server (the e2e webServer), not a minified
// build. entryFilter keeps just the app's own src/.
//
//   node scripts/gen-coverage.mjs <tier>      one tier's report
//   node scripts/gen-coverage.mjs --combined  every tier's captures in one
//
// Both write under test-artifacts/coverage/browser/. The tier is required
// because it used to be absent: the raw captures and the report both lived in
// one unkeyed directory, so `make coverage-demo` after `make coverage-e2e`
// silently replaced the e2e report with the demo one. `--combined` is the
// browser twin of `coverage combine` — a merge inside *this* tool, over its own
// captures. There is no cross-runtime union, which is why coverage/ holds a
// browser/ and a python/ subtree and no combined/ above them.

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { CoverageReport } from "monocart-coverage-reports";

// import.meta.dirname, not __dirname: this is a real ESM module, run by node
// directly. The Playwright-side helpers are the mirror image — package.json
// declares no "type", so Playwright's transform emits CommonJS and they anchor
// on __dirname instead (see tests/artifacts.ts). Neither form works in both
// places, which is why the two anchors cannot be one file.
const REPO_ROOT = join(import.meta.dirname, "..", "..");
const BROWSER_COVERAGE = join(REPO_ROOT, "test-artifacts", "coverage", "browser");
const RAW_ROOT = join(BROWSER_COVERAGE, "raw");

const arg = process.argv[2];
if (!arg) {
  console.error("usage: gen-coverage.mjs <tier> | --combined");
  process.exit(2);
}
const combined = arg === "--combined";

// A tier contributes only if it actually captured something: `unit` never drives
// a browser, and a stack tier that was never measured has no raw directory.
const tiers = combined
  ? (existsSync(RAW_ROOT) ? readdirSync(RAW_ROOT, { withFileTypes: true }) : [])
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .sort()
  : [arg];

const inputs = [];
for (const tier of tiers) {
  const dir = join(RAW_ROOT, tier);
  if (!existsSync(dir)) continue;
  for (const file of readdirSync(dir).filter((f) => f.endsWith(".json"))) {
    inputs.push(join(dir, file));
  }
}

if (inputs.length === 0) {
  console.error(`No per-test V8 captures under ${combined ? RAW_ROOT : join(RAW_ROOT, arg)}.`);
  console.error("Run a measured stack tier first: make coverage-e2e (or coverage-demo).");
  process.exit(1);
}

const label = combined ? `combined (${tiers.join(", ")})` : arg;
const outputDir = join(BROWSER_COVERAGE, combined ? "combined" : arg);

const report = new CoverageReport({
  name: `repo2ree — ${label} tier, browser`,
  outputDir,
  // v8: monocart's interactive single-page report (byte/branch/function/line,
  //   source-mapped) — the reason to use monocart over plain istanbul html.
  // console-summary: prints the totals table to the terminal on generate.
  // markdown-summary: a coverage.md table to paste into a PR / CI comment.
  // lcovonly: for Coverage Gutters in-editor and CI upload.
  reports: ["v8", "console-summary", "markdown-summary", "lcovonly"],
  // Filter by entry URL, not resolved source path: Vite's dev server serves the
  // app under /src/, while node_modules deps, /@vite/ + /@react-refresh/
  // internals, and the document root live elsewhere. (A sourceFilter on the
  // resolved path does not work here — Vite's dev sourcemaps carry only the
  // basename, e.g. "App.tsx", so "src/" never appears in the mapped path.)
  entryFilter: (entry) => entry.url.includes("/src/"),
});

for (const file of inputs) {
  await report.add(JSON.parse(readFileSync(file, "utf8")));
}

await report.generate();
// The console-summary reporter prints the totals table above; just point at the report.
console.log(`\nGUI ${label} coverage (${inputs.length} tests) -> ${outputDir}/index.html`);
