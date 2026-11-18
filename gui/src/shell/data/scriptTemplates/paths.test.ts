import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { ScriptTemplateCatalog } from "@shell/infra/api/apiTypes";
import { describe, expect, it } from "vitest";
import { experimentRunScriptPath, experimentVerifyScriptPath } from "./paths";

// The backend owns the slug rule (repo2ree_ree.reserved_paths.experiment_slug)
// and these helpers re-derive it so the editor can show the destination before
// the round-trip. Two implementations of one rule, so both sides assert against
// contracts/ree/fixtures/experiment-slugs.json — see
// ree/tests/test_experiment_slug_contract.py.
const fixture = JSON.parse(
  readFileSync(
    fileURLToPath(
      new URL("../../../../../contracts/ree/fixtures/experiment-slugs.json", import.meta.url),
    ),
    "utf-8",
  ),
) as { cases: Array<{ name: string; slug: string }> };

const catalog = {
  experiment_run: { path_pattern: "ree-scripts/experiments/{slug}.sh" },
  experiment_verify: { path_pattern: "ree-scripts/experiments/{slug}.verify.sh" },
} as unknown as ScriptTemplateCatalog;

describe("experiment script paths", () => {
  it.each(fixture.cases)("slugs %j to the backend's path", ({ name, slug }) => {
    expect(experimentRunScriptPath(catalog, name)).toBe(`ree-scripts/experiments/${slug}.sh`);
    expect(experimentVerifyScriptPath(catalog, name)).toBe(
      `ree-scripts/experiments/${slug}.verify.sh`,
    );
  });
});
