export const EXPECTED_DEP_FILES = [
  {
    label: "requirements.txt",
    hint: "pip — per-package pins",
    color: "#3b82f6",
  },
  { label: "pyproject.toml", hint: "pip / hatch / poetry", color: "#8b5cf6" },
  { label: "environment.yml", hint: "conda + bioconda", color: "#22c55e" },
  { label: "package.json", hint: "npm / yarn dependencies", color: "#dc2626" },
  { label: "Dockerfile", hint: "container environment", color: "#0891b2" },
  { label: "*.nix", hint: "declarative system env", color: "#7c3aed" },
] as const;
