import type { FileTreeNode } from "../workspace/FileTree";

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

const DEP_PARSERS: Record<string, (content: string) => DepPackage[]> = {
  "requirements.txt": (content) => {
    const pkgs: DepPackage[] = [];
    for (const raw of content.split("\n")) {
      const line = raw.replace(/#.*$/, "").trim();
      if (!line || line.startsWith("-") || line.startsWith("http")) continue;
      const m = line.match(/^([A-Za-z0-9_\-.]+)(\[.*?\])?\s*([!<>=~,\s0-9.*]+)?$/);
      if (!m) continue;
      const name = m[1];
      const version = (m[3] || "").trim() || null;
      pkgs.push({ name, version, raw: line, pinned: parsePinStatus(version) });
    }
    return pkgs;
  },
  "pyproject.toml": (content) => {
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
      const m = src.match(/^([A-Za-z0-9_\-.]+)(\[.*?\])?\s*([!<>=~,\s0-9.*"']+)?$/);
      if (!m) continue;
      const name = m[1];
      const version = (m[3] || "").replace(/["']/g, "").trim() || null;
      pkgs.push({ name, version, raw: src, pinned: parsePinStatus(version) });
    }
    return pkgs;
  },
  "environment.yml": (content) => {
    const pkgs: DepPackage[] = [];
    let inDeps = false;
    let inPip = false;
    for (const raw of content.split("\n")) {
      const line = raw.trim();
      if (line === "dependencies:") {
        inDeps = true;
        continue;
      }
      if (inDeps && line === "- pip:") {
        inPip = true;
        continue;
      }
      if (!inDeps) continue;
      if (line.startsWith("-") && !line.startsWith("- pip:")) {
        const entry = line
          .slice(1)
          .trim()
          .replace(/^["']|["']$/g, "");
        const m = entry.match(/^([A-Za-z0-9_\-.]+)\s*([=<>!~][=<>!~\s0-9.*]+)?$/);
        if (!m) continue;
        const name = m[1];
        const rawVer = (m[2] || "").trim() || null;
        const version = rawVer ? rawVer.replace(/^=(?!=)/, "==") : null;
        pkgs.push({
          name,
          version,
          raw: entry,
          pinned: parsePinStatus(version),
          ecosystem: inPip ? "pip" : "conda",
        });
      }
    }
    return pkgs;
  },
  "package.json": (content) => {
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
  },
  Pipfile: (content) => {
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
      const m = line.match(/^([A-Za-z0-9_\-.]+)\s*=\s*["']([^"']*)["']/);
      if (!m) continue;
      pkgs.push({
        name: m[1],
        version: m[2] === "*" ? null : m[2],
        raw: line,
        pinned: parsePinStatus(m[2] === "*" ? null : m[2]),
      });
    }
    return pkgs;
  },
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
  const results: DepGroup[] = [];
  for (const node of nodes || []) {
    const fullPath = path ? `${path}/${node.name}` : node.name;
    if (node.type === "folder") {
      results.push(...scanDependencies(node.children || [], fullPath));
    } else {
      const parser = getManifestParser(node.name);
      if (!parser) continue;
      const lower = node.name.toLowerCase();
      const eco =
        lower === "package.json"
          ? "npm"
          : lower === "pyproject.toml"
            ? "toml"
            : lower.includes("environment")
              ? "conda"
              : "pip";
      const packages = parser(node.content || "");
      if (packages.length > 0) {
        results.push({ file: node.name, path: fullPath, ecosystem: eco, packages });
      }
    }
  }
  return results;
}
