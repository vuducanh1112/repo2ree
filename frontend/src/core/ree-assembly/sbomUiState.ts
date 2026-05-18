// Pure derivations for the Generate SBOM page. Belongs in core (functional)
// so the shell does not parse domain artifacts itself.

const SBOM_PARSE_CHAR_LIMIT = 300_000;

const SKIPPED_SENTINEL = "__skipped__";

export function resolvedSbomPath(raw: string | null | undefined): string {
  return raw && raw !== SKIPPED_SENTINEL ? raw : "";
}

interface SbomFileLike {
  content?: string;
  size?: number;
}

export function isRuntimeTarballPath(path: string): boolean {
  return /\.(tar|tar\.gz|tgz)$/i.test(path);
}

interface SbomSummary {
  format: string | null;
  pkgCount: number | null;
}

export function summarizeSbom(file: SbomFileLike | null): SbomSummary {
  const parsed = parseSbomJson(file);
  if (!parsed) return { format: null, pkgCount: null };
  const format = parsed.spdxVersion
    ? String(parsed.spdxVersion)
    : parsed.bomFormat
      ? String(parsed.bomFormat)
      : parsed.artifacts
        ? "Syft JSON"
        : null;
  return { format, pkgCount: parsed.packages?.length ?? null };
}

interface ParsedSbom {
  packages?: unknown[];
  spdxVersion?: string;
  bomFormat?: string;
  artifacts?: unknown;
}

function parseSbomJson(file: SbomFileLike | null): ParsedSbom | null {
  if (!file?.content || file.content.length > SBOM_PARSE_CHAR_LIMIT) return null;
  try {
    return JSON.parse(file.content) as ParsedSbom;
  } catch {
    return null;
  }
}

export function sbomReadiness(input: {
  hasRuntime: boolean;
  runtimePathExists: boolean;
  hasSbom: boolean;
}) {
  const checks = [input.hasRuntime, input.runtimePathExists, input.hasSbom];
  const done = checks.filter(Boolean).length;
  return {
    ...input,
    done,
    total: checks.length,
    percent: Math.round((done / checks.length) * 100),
  };
}
