import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { PAGE } from "@core/app-shell/pages";
import { describe, expect, it } from "vitest";
import {
  archiveTone,
  axisTone,
  dependencyStatusTone,
  ecosystemTone,
  failureTone,
  stageTone,
  translucent,
} from "./appearance";

const tones = readFileSync(fileURLToPath(new URL("./tones.css", import.meta.url)), "utf8");

const declared = (reference: string): boolean => {
  const name = reference.slice("var(".length, -1);
  return tones.includes(`\n  ${name}:`);
};

describe("appearance", () => {
  it("resolves every stage to a declared tone", () => {
    const stages = Object.values(PAGE).filter(
      (page) => page !== PAGE.CANVAS && page !== PAGE.WORKBENCH,
    );
    for (const stage of stages) {
      expect(declared(stageTone(stage)), `${stage} line`).toBe(true);
      expect(declared(stageTone(stage, "ink")), `${stage} ink`).toBe(true);
    }
  });

  it("resolves the wash of every stage that shows an earned-outcome chip", () => {
    for (const stage of [
      PAGE.EVALUATE_REPRODUCIBILITY,
      PAGE.BUILD_EXPERIMENT_ENVIRONMENT,
      PAGE.OBSERVE_HARDWARE,
      PAGE.GENERATE_SBOM,
      PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT,
    ]) {
      expect(declared(stageTone(stage, "wash")), `${stage} wash`).toBe(true);
    }
  });

  it("resolves every axis, ecosystem, pinning status, archive and failure tone", () => {
    for (const axis of ["dependency", "environment", "machine"] as const) {
      for (const role of ["line", "ink"] as const) {
        expect(declared(axisTone(axis, role)), `${axis} ${role}`).toBe(true);
      }
    }
    for (const eco of ["pypi", "conda", "npm", "apt", "oci", "other"] as const) {
      for (const role of ["line", "wash"] as const) {
        expect(declared(ecosystemTone(eco, role)), `${eco} ${role}`).toBe(true);
      }
    }
    for (const status of ["locked", "pinned", "ranged", "unpinned", "undeclared"] as const) {
      for (const role of ["line", "wash", "edge"] as const) {
        expect(declared(dependencyStatusTone(status, role)), `${status} ${role}`).toBe(true);
      }
    }
    for (const repo of ["swh", "zenodo", "dataverse"] as const) {
      expect(declared(archiveTone(repo)), `${repo} line`).toBe(true);
    }
    for (const tone of ["transient", "rejected", "fault"] as const) {
      expect(declared(failureTone(tone)), tone).toBe(true);
    }
  });

  it("composes alpha instead of appending it, which a var() reference cannot take", () => {
    expect(translucent(stageTone(PAGE.ACQUIRE_SOURCE), 25)).toBe(
      "color-mix(in srgb, var(--stage-acquire_source-line) 25%, transparent)",
    );
  });
});
