import { describe, expect, it } from "vitest";
import { classifyFileType, normalizeSnapshotArchiveName, splitDisplayPath } from "./PathUtils";

describe("normalizeSnapshotArchiveName", () => {
  it("falls back to a default name when blank", () => {
    expect(normalizeSnapshotArchiveName("  ")).toBe("source.tar.gz");
  });

  it("preserves an existing .tar.gz name", () => {
    expect(normalizeSnapshotArchiveName("project.tar.gz")).toBe("project.tar.gz");
  });

  it("rewrites other archive extensions to .tar.gz", () => {
    expect(normalizeSnapshotArchiveName("project.tgz")).toBe("project.tar.gz");
    expect(normalizeSnapshotArchiveName("project.zip")).toBe("project.tar.gz");
  });
});

describe("splitDisplayPath", () => {
  it("splits a nested path into prefix and base name", () => {
    expect(splitDisplayPath("src/app/main.py")).toEqual({
      dirPrefix: "src/app/",
      baseName: "main.py",
    });
  });

  it("yields an empty prefix for a bare name", () => {
    expect(splitDisplayPath("Dockerfile")).toEqual({ dirPrefix: "", baseName: "Dockerfile" });
  });

  it("keeps the leading slash of an absolute path in the prefix", () => {
    expect(splitDisplayPath("/main.py")).toEqual({ dirPrefix: "/", baseName: "main.py" });
  });

  it("yields an empty base name for a trailing slash", () => {
    expect(splitDisplayPath("src/")).toEqual({ dirPrefix: "src/", baseName: "" });
  });
});

describe("classifyFileType", () => {
  it("recognizes Dockerfiles as containers", () => {
    expect(classifyFileType("Dockerfile")).toBe("container");
    expect(classifyFileType("api.dockerfile")).toBe("container");
  });

  it("recognizes archives, including multi-part extensions", () => {
    expect(classifyFileType("source.tar.gz")).toBe("archive");
    expect(classifyFileType("wheel-1.0.whl")).toBe("archive");
  });

  it("buckets code, data, and doc extensions", () => {
    expect(classifyFileType("main.py")).toBe("code");
    expect(classifyFileType("config.yaml")).toBe("data");
    expect(classifyFileType("README.md")).toBe("doc");
  });

  it("falls back to binary for unknown or extensionless names", () => {
    expect(classifyFileType("photo.png")).toBe("binary");
    expect(classifyFileType("LICENSE")).toBe("binary");
  });
});
