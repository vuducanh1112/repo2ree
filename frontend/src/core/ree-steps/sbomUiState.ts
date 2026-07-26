// Pure derivations for the Generate SBOM page. Belongs in core (functional)
// so the shell does not parse domain artifacts itself.

import type { ReeFile } from "../ree/ReeTypes";

const SBOM_PARSE_CHAR_LIMIT = 300_000;

const SKIPPED_SENTINEL = "__skipped__";

/**
 * Where the REE keeps its SBOM, REE-root-relative.
 *
 * Backend-owned (``repo2ree_core.storage.layout.SBOM_ARTIFACT_PATH``): the
 * generate-sbom step writes there and publishes this exact path on the intent,
 * and a bundle carries it at the same path. It is REE evidence, not an authored
 * workspace file, so it is looked up among the REE's artifact files.
 */
export const SBOM_ARTIFACT_PATH = "artifacts/sbom.json";

export function resolvedSbomPath(raw: string | null | undefined): string {
  return raw && raw !== SKIPPED_SENTINEL ? raw : "";
}

interface SbomFileLike {
  content?: string;
  size?: number;
}

/** The SBOM among the REE's own artifacts, or null when the scan has not run. */
export function findSbomArtifact(reeFiles: ReeFile[], path: string): ReeFile | null {
  if (!path) return null;
  return reeFiles.find((file) => file.name === path) ?? null;
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
  if (parsed.bomFormat === "CycloneDX") {
    const version = parsed.specVersion ? ` ${String(parsed.specVersion)}` : "";
    return {
      format: `CycloneDX${version}`,
      pkgCount: Array.isArray(parsed.components) ? parsed.components.length : null,
    };
  }
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
  specVersion?: string;
  components?: unknown[];
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
