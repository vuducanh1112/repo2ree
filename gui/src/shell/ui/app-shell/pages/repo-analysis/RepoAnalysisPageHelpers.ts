/** The dependency manifests the evaluator looks for. `kind` selects how each
 * one reads; RepoAnalysisPage.module.css owns the colours. */
export const EXPECTED_DEP_FILES = [
  { label: "requirements.txt", hint: "pip — per-package pins", kind: "pip" },
  { label: "pyproject.toml", hint: "pip / hatch / poetry", kind: "pyproject" },
  { label: "environment.yml", hint: "conda + bioconda", kind: "conda" },
  { label: "package.json", hint: "npm / yarn dependencies", kind: "npm" },
  { label: "Dockerfile", hint: "container environment", kind: "container" },
  { label: "*.nix", hint: "declarative system env", kind: "nix" },
] as const;
