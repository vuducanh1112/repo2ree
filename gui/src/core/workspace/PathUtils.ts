export function normalizeSnapshotArchiveName(rawName: string): string {
  const trimmed = (rawName || "").trim();
  if (!trimmed) return "source.tar.gz";
  if (/\.tar\.gz$/i.test(trimmed)) return trimmed;
  if (/\.tgz$/i.test(trimmed)) return trimmed.replace(/\.tgz$/i, ".tar.gz");
  const stem = trimmed.replace(/\.(zip|tar|tar\.bz2|tar\.xz|tar\.zst|jar)$/i, "");
  return `${stem || "source"}.tar.gz`;
}

/**
 * Coarse content-type bucket for a file name, used to pick a file-browser icon
 * and the tint its module gives that icon. Presentational only — it never
 * affects file handling. Returns "binary" for anything unrecognized.
 *
 * Not exported: the shell renders the value as a `data-category` attribute and
 * never names the type, which is the point of keying CSS off the identity.
 */
type FileTypeCategory = "code" | "data" | "doc" | "container" | "archive" | "binary";

const CODE_EXTENSIONS = new Set([
  "py",
  "js",
  "ts",
  "tsx",
  "jsx",
  "mjs",
  "cjs",
  "sh",
  "bash",
  "go",
  "rs",
  "rb",
  "java",
  "c",
  "cc",
  "cpp",
  "h",
  "hpp",
]);

const DATA_EXTENSIONS = new Set([
  "json",
  "yaml",
  "yml",
  "toml",
  "xml",
  "ini",
  "cfg",
  "conf",
  "csv",
  "env",
  "lock",
]);

const DOC_EXTENSIONS = new Set(["md", "rst", "txt", "log"]);

/**
 * Split a display path into a trailing base name and the directory prefix that
 * precedes it (including the separating slash, e.g. "src/app/"). Used by the
 * file viewer to render the directory dimly and the base name emphasized. Paths
 * without a slash yield an empty prefix; a trailing slash yields an empty base
 * name.
 */
export function splitDisplayPath(path: string): { dirPrefix: string; baseName: string } {
  const slash = path.lastIndexOf("/");
  if (slash < 0) return { dirPrefix: "", baseName: path };
  return { dirPrefix: path.slice(0, slash + 1), baseName: path.slice(slash + 1) };
}

export function classifyFileType(fileName: string): FileTypeCategory {
  const lower = (fileName || "").toLowerCase();
  if (lower === "dockerfile" || lower.endsWith(".dockerfile")) return "container";
  if (/\.(tar\.gz|tgz|tar|zip|whl|gz|bz2|xz|zst|jar)$/.test(lower)) return "archive";
  const ext = lower.includes(".") ? lower.split(".").pop() || "" : "";
  if (CODE_EXTENSIONS.has(ext)) return "code";
  if (DATA_EXTENSIONS.has(ext)) return "data";
  if (DOC_EXTENSIONS.has(ext)) return "doc";
  return "binary";
}
