import { LEVELS } from "../../constants/levels";
import type { FileTreeNode } from "../../types/workspace";
import { listTreeFiles } from "../../utils";

export type PinStatus = "exact" | "range" | "none";

export interface DepPackage {
  name: string;
  version: string | null;
  raw: string;
  pinned: PinStatus;
  dev?: boolean;
  ecosystem?: string;
}

export interface DepGroup {
  file: string;
  path: string;
  ecosystem: string;
  packages: DepPackage[];
}

interface EcoMeta {
  label: string;
  color: string;
  bg: string;
}

export const ECO_META: Record<string, EcoMeta> = {
  pip: { label: "pip", color: "#3b82f6", bg: "#eff6ff" },
  conda: { label: "conda", color: "#22c55e", bg: "#f0fdf4" },
  npm: { label: "npm", color: "#dc2626", bg: "#fef2f2" },
  toml: { label: "toml", color: "#8b5cf6", bg: "#f5f3ff" },
  dev: { label: "dev", color: "#f59e0b", bg: "#fffbeb" },
};

interface PinMeta {
  label: string;
  color: string;
  bg: string;
  border: string;
}

export const PIN_META: Record<PinStatus, PinMeta> = {
  exact: { label: "pinned", color: "#16a34a", bg: "#dcfce7", border: "#86efac" },
  range: { label: "range", color: "#d97706", bg: "#fef3c7", border: "#fcd34d" },
  none: { label: "unpinned", color: "#dc2626", bg: "#fef2f2", border: "#fca5a5" },
};

function parsePinStatus(version: string | null | undefined): PinStatus {
  if (!version) return "none";
  if (/^[=~^]?[0-9]/.test(version) && version.includes("==")) return "exact";
  if (/[=<>~^]/.test(version)) return "range";
  if (/^[0-9]/.test(version)) return "exact";
  return "none";
}

function parseDependencySpec(src: string): { name: string; version: string | null } | null {
  const match = src.match(/^([A-Za-z0-9_\-.]+)(\[.*?\])?\s*([!<>=~,\s0-9.*"']+)?$/);
  if (!match) return null;
  const name = match[1];
  const version = (match[3] || "").replace(/["']/g, "").trim() || null;
  return { name, version };
}

function parseEnvironmentDependencyEntry(
  entry: string,
): { name: string; version: string | null } | null {
  const match = entry.match(/^([A-Za-z0-9_\-.]+)\s*([=<>!~][=<>!~\s0-9.*]+)?$/);
  if (!match) return null;
  const name = match[1];
  const rawVersion = (match[2] || "").trim() || null;
  const version = rawVersion ? rawVersion.replace(/^=(?!=)/, "==") : null;
  return { name, version };
}

function getEcosystemFromFilename(filename: string): string {
  const lower = filename.toLowerCase();
  if (lower === "package.json") return "npm";
  if (lower === "pyproject.toml") return "toml";
  if (lower.includes("environment")) return "conda";
  return "pip";
}

function scanDependenciesAtPath(nodes: FileTreeNode[], path = ""): DepGroup[] {
  const results: DepGroup[] = [];
  for (const node of nodes || []) {
    const fullPath = path ? `${path}/${node.name}` : node.name;
    if (node.type === "folder") {
      results.push(...scanDependenciesAtPath(node.children || [], fullPath));
      continue;
    }

    const parser = getManifestParser(node.name);
    if (!parser) continue;

    const packages = parser(node.content || "");
    if (packages.length === 0) continue;
    results.push({
      file: node.name,
      path: fullPath,
      ecosystem: getEcosystemFromFilename(node.name),
      packages,
    });
  }
  return results;
}

function parseRequirements(content: string): DepPackage[] {
  const pkgs: DepPackage[] = [];
  for (const raw of content.split("\n")) {
    const line = raw.replace(/#.*$/, "").trim();
    if (!line || line.startsWith("-") || line.startsWith("http")) continue;
    const match = line.match(/^([A-Za-z0-9_\-.]+)(\[.*?\])?\s*([!<>=~,\s0-9.*]+)?$/);
    if (!match) continue;
    const name = match[1];
    const version = (match[3] || "").trim() || null;
    pkgs.push({ name, version, raw: line, pinned: parsePinStatus(version) });
  }
  return pkgs;
}

function parsePyproject(content: string): DepPackage[] {
  const pkgs: DepPackage[] = [];
  let inDeps = false;

  for (const raw of content.split("\n")) {
    const line = raw.trim();
    if (line === "[project.dependencies]" || line === "dependencies = [") {
      inDeps = true;
      continue;
    }
    if (inDeps && line.startsWith("[") && !line.startsWith("dependencies")) {
      inDeps = false;
    }

    const quoted = line.match(/^["']([^"']+)["'],?$/);
    const src = quoted?.[1] || (inDeps ? line.replace(/,$/, "") : null);
    if (!src) continue;

    const parsed = parseDependencySpec(src);
    if (!parsed) continue;

    pkgs.push({
      name: parsed.name,
      version: parsed.version,
      raw: src,
      pinned: parsePinStatus(parsed.version),
    });
  }

  return pkgs;
}

function parseEnvironment(content: string): DepPackage[] {
  const pkgs: DepPackage[] = [];
  let inDeps = false;
  let inPip = false;

  for (const raw of content.split("\n")) {
    const line = raw.trim();
    if (line === "dependencies:") {
      inDeps = true;
      continue;
    }
    if (!inDeps) continue;
    if (line === "- pip:") {
      inPip = true;
      continue;
    }
    if (!line.startsWith("-") || line.startsWith("- pip:")) continue;

    const entry = line
      .slice(1)
      .trim()
      .replace(/^["']|["']$/g, "");
    const parsed = parseEnvironmentDependencyEntry(entry);
    if (!parsed) continue;

    pkgs.push({
      name: parsed.name,
      version: parsed.version,
      raw: entry,
      pinned: parsePinStatus(parsed.version),
      ecosystem: inPip ? "pip" : "conda",
    });
  }

  return pkgs;
}

function parsePackageJson(content: string): DepPackage[] {
  try {
    const obj = JSON.parse(content) as {
      dependencies?: Record<string, string>;
      devDependencies?: Record<string, string>;
    };
    const pkgs: DepPackage[] = [];
    const add = (deps: Record<string, string> | undefined, dev: boolean) => {
      for (const [name, version] of Object.entries(deps || {})) {
        pkgs.push({
          name,
          version,
          raw: `${name}: ${version}`,
          pinned: parsePinStatus(version),
          dev,
        });
      }
    };
    add(obj.dependencies, false);
    add(obj.devDependencies, true);
    return pkgs;
  } catch {
    return [];
  }
}

function parsePipfile(content: string): DepPackage[] {
  const pkgs: DepPackage[] = [];
  let inSection = false;
  for (const raw of content.split("\n")) {
    const line = raw.trim();
    if (line === "[packages]" || line === "[dev-packages]") {
      inSection = true;
      continue;
    }
    if (line.startsWith("[") && line !== "[packages]" && line !== "[dev-packages]") {
      inSection = false;
    }
    if (!inSection) continue;
    const match = line.match(/^([A-Za-z0-9_\-.]+)\s*=\s*["']([^"']*)["']/);
    if (!match) continue;
    pkgs.push({
      name: match[1],
      version: match[2] === "*" ? null : match[2],
      raw: line,
      pinned: parsePinStatus(match[2] === "*" ? null : match[2]),
    });
  }
  return pkgs;
}

const DEP_PARSERS: Record<string, (content: string) => DepPackage[]> = {
  "requirements.txt": parseRequirements,
  "pyproject.toml": parsePyproject,
  "environment.yml": parseEnvironment,
  "package.json": parsePackageJson,
  Pipfile: parsePipfile,
};

function getManifestParser(filename: string): ((content: string) => DepPackage[]) | null {
  const lower = filename.toLowerCase();
  if (lower === "requirements.txt" || /^requirements[-_].+\.txt$/.test(lower)) {
    return DEP_PARSERS["requirements.txt"];
  }
  if (lower === "pyproject.toml") return DEP_PARSERS["pyproject.toml"];
  if (lower === "environment.yml" || lower === "environment.yaml") {
    return DEP_PARSERS["environment.yml"];
  }
  if (lower === "package.json") return DEP_PARSERS["package.json"];
  if (lower === "pipfile") return DEP_PARSERS.Pipfile;
  return null;
}

export function scanDependencies(nodes: FileTreeNode[], path = ""): DepGroup[] {
  return scanDependenciesAtPath(nodes, path);
}

export function computeEvaluateLevelFromFiles(nodes: FileTreeNode[]): number {
  const files = nodes || [];
  const allPaths = listTreeFiles(files).map((entry) => entry.path.toLowerCase());
  const hasReadme = allPaths.some(
    (path) => path.endsWith("readme.md") || path.endsWith("readme.txt"),
  );

  const manifestPaths = allPaths.filter((path) => {
    const base = path.split("/").pop() || "";
    return !!getManifestParser(base);
  });
  const hasManifest = manifestPaths.length > 0;

  const depGroups = scanDependencies(files);
  const deps = depGroups.flatMap((group) => group.packages);
  const hasTopPins = deps.some((dep) => dep.pinned === "exact");

  const lockFiles = new Set([
    "poetry.lock",
    "pipfile.lock",
    "uv.lock",
    "pdm.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "conda-lock.yml",
    "conda-lock.yaml",
  ]);
  const hasLockfile = allPaths.some((path) => lockFiles.has(path.split("/").pop() || ""));

  const hasContainer = allPaths.some((path) => {
    const name = path.split("/").pop() || "";
    return (
      name === "dockerfile" ||
      name === "containerfile" ||
      name.startsWith("dockerfile.") ||
      name.startsWith("containerfile.") ||
      name === "docker-compose.yml" ||
      name === "docker-compose.yaml"
    );
  });

  const hasNix = allPaths.some((path) => path.endsWith(".nix"));
  const hasBeyondSignals = allPaths.some((path) => {
    const name = path.split("/").pop() || "";
    return (
      name.includes("reproduc") ||
      name.includes("determin") ||
      name.includes("provenance") ||
      name.includes("hardware") ||
      name.includes("swhid")
    );
  });

  let level = 0;
  if (hasReadme) level = 1;
  if (hasManifest) level = 2;
  if (hasTopPins) level = 3;
  if (hasLockfile) level = 4;
  if (hasContainer) level = 5;
  if (hasNix) level = 6;
  if (hasNix && hasBeyondSignals) level = 7;

  return Math.max(0, Math.min(level, LEVELS.length - 1));
}
