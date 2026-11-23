import type { ScriptTemplateCatalog } from "@shell/infra/api/apiTypes";

function experimentSlug(name: string): string {
  return name.trim().replace(/\s+/g, "-") || "experiment";
}

export function experimentRunScriptPath(
  catalog: ScriptTemplateCatalog,
  experimentName: string,
): string {
  return catalog.experiment_run.path_pattern.replace("{slug}", experimentSlug(experimentName));
}

export function experimentVerifyScriptPath(
  catalog: ScriptTemplateCatalog,
  experimentName: string,
): string {
  return catalog.experiment_verify.path_pattern.replace("{slug}", experimentSlug(experimentName));
}
