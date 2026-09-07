export interface DisplayBuildInfo {
  version?: string;
  revision?: string;
}

export function revisionLabel(revision?: string): string {
  if (!revision) return "development";
  if (revision === "development") return revision;
  const dirty = revision.endsWith("-dirty");
  const hash = dirty ? revision.slice(0, -6) : revision;
  return `${hash.slice(0, 8)}${dirty ? "-dirty" : ""}`;
}

export function buildTitle(component: string, build: DisplayBuildInfo): string {
  const version = build.version ? `v${build.version} · ` : "";
  return `${component}: ${version}${build.revision || "development build (revision unavailable)"}`;
}
