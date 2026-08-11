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
  presenceTone,
  stageTone,
  translucent,
} from "./appearance";

// A tone reference that names nothing is the migration's quietest failure: CSS
// drops the declaration, the element renders unstyled, and nothing throws. So
// the mappings are checked against the stylesheet that has to declare them.
const tones = readFileSync(fileURLToPath(new URL("./tones.css", import.meta.url)), "utf8");

const declared = (reference: string): boolean => {
  const name = reference.slice("var(".length, -1);
  return tones.includes(`\n  ${name}:`);
};

describe("appearance", () => {
  it("resolves every stage to a declared tone", () => {
    // The canvas ring and the run catalog between them use every page key, and
    // `line`/`ink` are what a cable needs, so both are required for all of them.
    const stages = Object.values(PAGE).filter(
      (page) => page !== PAGE.CANVAS && page !== PAGE.WORKBENCH,
    );
    for (const stage of stages) {
      expect(declared(stageTone(stage)), `${stage} line`).toBe(true);
      expect(declared(stageTone(stage, "ink")), `${stage} ink`).toBe(true);
    }
  });

  it("resolves the wash of every stage that shows an earned-outcome chip", () => {
    for (const stage of [PAGE.EVALUATE, PAGE.BUILD, PAGE.HBOM, PAGE.SBOM, PAGE.ACTIVATION]) {
      expect(declared(stageTone(stage, "wash")), `${stage} wash`).toBe(true);
    }
  });

  it("resolves every axis, ecosystem, pinning status, presence, archive and failure tone", () => {
    for (const axis of ["dependency", "environment", "machine"] as const) {
      for (const role of ["line", "wash", "ink"] as const) {
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
    for (const presence of ["observed", "version-mismatch", "not-observed"] as const) {
      for (const role of ["line", "wash", "edge"] as const) {
        expect(declared(presenceTone(presence, role)), `${presence} ${role}`).toBe(true);
      }
    }
    for (const repo of ["swh", "zenodo", "dataverse"] as const) {
      for (const role of ["line", "wash", "edge"] as const) {
        expect(declared(archiveTone(repo, role)), `${repo} ${role}`).toBe(true);
      }
    }
    for (const tone of ["transient", "rejected", "fault"] as const) {
      expect(declared(failureTone(tone)), tone).toBe(true);
    }
  });

  it("composes alpha instead of appending it, which a var() reference cannot take", () => {
    expect(translucent(stageTone(PAGE.SOURCE), 25)).toBe(
      "color-mix(in srgb, var(--stage-source-line) 25%, transparent)",
    );
  });
});
