import { describe, expect, it } from "vitest";
import { isRuntimeTarballPath, sbomReadiness, summarizeSbom } from "./sbomUiState";

describe("isRuntimeTarballPath", () => {
  it("matches tar, tar.gz, tgz regardless of case", () => {
    expect(isRuntimeTarballPath("runtime.tar")).toBe(true);
    expect(isRuntimeTarballPath("runtime.tar.gz")).toBe(true);
    expect(isRuntimeTarballPath("runtime.TGZ")).toBe(true);
    expect(isRuntimeTarballPath("runtime.zip")).toBe(false);
    expect(isRuntimeTarballPath("")).toBe(false);
  });
});

describe("summarizeSbom", () => {
  it("parses SPDX-shaped JSON", () => {
    const file = {
      content: JSON.stringify({ spdxVersion: "SPDX-2.3", packages: [{}, {}, {}] }),
    };
    expect(summarizeSbom(file)).toEqual({ format: "SPDX-2.3", pkgCount: 3 });
  });
  it("recognises CycloneDX and Syft", () => {
    expect(summarizeSbom({ content: JSON.stringify({ bomFormat: "CycloneDX" }) })).toEqual({
      format: "CycloneDX",
      pkgCount: null,
    });
    expect(summarizeSbom({ content: JSON.stringify({ artifacts: [] }) })).toEqual({
      format: "Syft JSON",
      pkgCount: null,
    });
  });
  it("returns nulls on invalid JSON, missing file, or too-large content", () => {
    expect(summarizeSbom(null)).toEqual({ format: null, pkgCount: null });
    expect(summarizeSbom({ content: "not json" })).toEqual({ format: null, pkgCount: null });
    expect(summarizeSbom({ content: "x".repeat(400_000) })).toEqual({
      format: null,
      pkgCount: null,
    });
  });
});

describe("sbomReadiness", () => {
  it("computes percent and counts", () => {
    const r = sbomReadiness({
      hasRuntime: true,
      runtimePathExists: true,
      hasSbom: false,
    });
    expect(r.done).toBe(2);
    expect(r.total).toBe(3);
    expect(r.percent).toBe(67);
  });
});
