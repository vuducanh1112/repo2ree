import type { ScriptTemplateCatalog } from "@shell/infra/api/apiTypes";

// Reserved script paths are backend-owned. The backend settles an experiment's
// run-script path on the intent when it is named; these helpers only exist so
// the UI can show (and save to) the same destination before that round-trip,
// by substituting the catalog's published `{slug}` patterns. The slug rule
// mirrors the backend's: whitespace collapses to hyphens.
function experimentSlug(name: string): string {
  return name.trim().replace(/\s+/g, "-") || "experiment";
}

export function experimentRunScriptPath(
  catalog: ScriptTemplateCatalog,
  experimentName: string,
): string {
  return catalog.experiment.run_script_path_pattern.replace(
    "{slug}",
    experimentSlug(experimentName),
  );
}

export function experimentVerifyScriptPath(
  catalog: ScriptTemplateCatalog,
  experimentName: string,
): string {
  return catalog.experiment.verify_script_path_pattern.replace(
    "{slug}",
    experimentSlug(experimentName),
  );
}
