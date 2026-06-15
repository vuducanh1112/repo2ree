// Merge the per-test browser V8 coverage captured by the e2e suite (written by
// the jsCoverage fixture when E2E_COVERAGE is set) into one istanbul/lcov +
// HTML report. Run after the Playwright e2e run; `make e2e-coverage` does both.
//
// V8 -> source mapping leans on the Vite dev server's sourcemaps, so this is
// meaningful only against the dev server (the e2e webServer), not a minified
// build. sourceFilter keeps just the app's own src/.

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { CoverageReport } from "monocart-coverage-reports";

const cwd = process.cwd();
const rawDir = join(cwd, "test-results", "e2e-coverage", "raw");
const outputDir = join(cwd, "coverage", "frontend");

if (!existsSync(rawDir)) {
  console.error(`No raw coverage at ${rawDir}.`);
  console.error("Run the e2e suite with E2E_COVERAGE=1 first (or use `make e2e-coverage`).");
  process.exit(1);
}

const rawFiles = readdirSync(rawDir).filter((f) => f.endsWith(".json"));
if (rawFiles.length === 0) {
  console.error(`No per-test coverage files in ${rawDir}.`);
  process.exit(1);
}

const report = new CoverageReport({
  name: "repo2ree frontend e2e coverage",
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

for (const file of rawFiles) {
  const entries = JSON.parse(readFileSync(join(rawDir, file), "utf8"));
  await report.add(entries);
}

await report.generate();
// The console-summary reporter prints the totals table above; just point at the report.
console.log(`\nFrontend e2e coverage (${rawFiles.length} tests) -> ${outputDir}/index.html`);
