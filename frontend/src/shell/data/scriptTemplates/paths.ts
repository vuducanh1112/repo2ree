import type { ScriptTemplateCatalogDto } from "@shell/infra/api/apiTypes";

// Reserved script paths are backend-owned. The backend settles an experiment's
// run-script path on the intent when it is named; these helpers only exist so
// the UI can show (and save to) the same destination before that round-trip,
// by substituting the catalog's published `{slug}` patterns. The slug rule
// mirrors the backend's: whitespace collapses to hyphens.
function experimentSlug(name: string): string {
  return name.trim().replace(/\s+/g, "-") || "experiment";
}

export function experimentRunScriptPath(
  catalog: ScriptTemplateCatalogDto,
  experimentName: string,
): string {
  return catalog.experiment.runScriptPathPattern.replace("{slug}", experimentSlug(experimentName));
}

export function experimentVerifyScriptPath(
  catalog: ScriptTemplateCatalogDto,
  experimentName: string,
): string {
  return catalog.experiment.verifyScriptPathPattern.replace(
    "{slug}",
    experimentSlug(experimentName),
  );
}
