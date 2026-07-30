import { describe, expect, it } from "vitest";
import { fileType, fmtBytes } from "./formatting";

describe("fmtBytes", () => {
  it("stays in bytes below a kilobyte", () => {
    expect(fmtBytes(0)).toBe("0 B");
    expect(fmtBytes(1023)).toBe("1023 B");
  });

  it("switches unit exactly at each 1024 boundary", () => {
    expect(fmtBytes(1024)).toBe("1.0 KB");
    expect(fmtBytes(1024 * 1024 - 1)).toBe("1024.0 KB");
    expect(fmtBytes(1024 * 1024)).toBe("1.00 MB");
  });

  it("keeps one decimal for KB and two for MB", () => {
    expect(fmtBytes(1536)).toBe("1.5 KB");
    expect(fmtBytes(5 * 1024 * 1024 + 512 * 1024)).toBe("5.50 MB");
  });

  it("has no ceiling — a runtime tarball reads in MB, not GB", () => {
    // The 327 MB runtime the examples README describes is the realistic top end.
    expect(fmtBytes(327 * 1024 * 1024)).toBe("327.00 MB");
  });
});

describe("fileType", () => {
  it("recognises Dockerfiles by name, with or without an extension", () => {
    expect(fileType("Dockerfile")).toBe("dockerfile");
    expect(fileType("docker/prod.dockerfile")).toBe("dockerfile");
    expect(fileType("path/to/CONTAINERFILE")).toBe("dockerfile");
  });

  it("classifies the languages the pipeline actually writes", () => {
    expect(fileType("ree-scripts/build.sh")).toBe("shell");
    expect(fileType("main.py")).toBe("python");
    expect(fileType("artifacts/sbom.json")).toBe("json");
    expect(fileType("flake.nix")).toBe("nix");
    expect(fileType("README.md")).toBe("markdown");
  });

  it("groups lockfiles and config formats together", () => {
    expect(fileType("uv.lock")).toBe("config");
    expect(fileType("pyproject.toml")).toBe("config");
    expect(fileType("docker-compose.yml")).toBe("config");
  });

  it("falls back to text for anything unknown or unnamed", () => {
    expect(fileType("")).toBe("text");
    expect(fileType("result.bin")).toBe("text");
    expect(fileType("LICENSE")).toBe("text");
  });

  it("reads the extension, not the directory it sits in", () => {
    expect(fileType("py/notes.md")).toBe("markdown");
  });
});
