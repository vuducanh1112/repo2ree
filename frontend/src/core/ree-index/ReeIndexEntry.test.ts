import { describe, expect, it } from "vitest";
import {
  type ArchiveBinding,
  archiveLabel,
  isDeposited,
  primaryBinding,
  type ReeIndexEntry,
  shortDigest,
  sortReeIndexEntries,
} from "./ReeIndexEntry";

function binding(overrides: Partial<ArchiveBinding> = {}): ArchiveBinding {
  return {
    archive: "zenodo",
    identifier: "doi:10.5281/zenodo.1",
    recordUrl: "",
    conceptIdentifier: "",
    version: "",
    signedAt: "",
    ...overrides,
  };
}

function entry(overrides: Partial<ReeIndexEntry> = {}): ReeIndexEntry {
  return {
    subjectDigest: "sha256:aaaaaaaaaaaaaaaa",
    name: "demo",
    sealedAt: "2026-07-29T00:00:00Z",
    description: "",
    keywords: [],
    reeVersion: "1",
    archiveBindings: [],
    ...overrides,
  };
}

describe("isDeposited", () => {
  it("is false for a seal no archive has accepted", () => {
    expect(isDeposited(entry())).toBe(false);
  });

  it("is true once any binding exists", () => {
    expect(isDeposited(entry({ archiveBindings: [binding()] }))).toBe(true);
  });
});

describe("primaryBinding", () => {
  it("is undefined for a local seal", () => {
    expect(primaryBinding(entry())).toBeUndefined();
  });

  it("prefers a citable DOI over an intrinsic identifier", () => {
    const swh = binding({ archive: "software_heritage", identifier: "swh:1:dir:abc" });
    const result = primaryBinding(entry({ archiveBindings: [swh, binding()] }));

    expect(result?.archive).toBe("zenodo");
  });

  it("falls back to the only binding when that is all there is", () => {
    const swh = binding({ archive: "software_heritage", identifier: "swh:1:dir:abc" });

    expect(primaryBinding(entry({ archiveBindings: [swh] }))?.identifier).toBe("swh:1:dir:abc");
  });
});

describe("shortDigest", () => {
  it("drops the algorithm prefix and truncates", () => {
    expect(shortDigest("sha256:0123456789abcdef0123")).toBe("0123456789ab");
  });

  it("passes through a digest carrying no prefix", () => {
    expect(shortDigest("0123456789abcdef")).toBe("0123456789ab");
  });
});

describe("archiveLabel", () => {
  it("names each archive the backend can record", () => {
    expect(archiveLabel("software_heritage")).toBe("Software Heritage");
    expect(archiveLabel("zenodo")).toBe("Zenodo");
    expect(archiveLabel("dataverse")).toBe("Dataverse");
  });
});

describe("sortReeIndexEntries", () => {
  it("puts the newest seal first", () => {
    const older = entry({ subjectDigest: "sha256:bbb", sealedAt: "2026-07-28T00:00:00Z" });
    const newer = entry({ subjectDigest: "sha256:aaa", sealedAt: "2026-07-29T00:00:00Z" });

    expect(sortReeIndexEntries([older, newer]).map((e) => e.subjectDigest)).toEqual([
      "sha256:aaa",
      "sha256:bbb",
    ]);
  });

  it("breaks a tied seal time by digest so rows cannot swap between renders", () => {
    const b = entry({ subjectDigest: "sha256:bbb" });
    const a = entry({ subjectDigest: "sha256:aaa" });

    expect(sortReeIndexEntries([b, a]).map((e) => e.subjectDigest)).toEqual([
      "sha256:aaa",
      "sha256:bbb",
    ]);
  });

  it("does not mutate its input", () => {
    const entries = [
      entry({ subjectDigest: "sha256:bbb" }),
      entry({ subjectDigest: "sha256:aaa" }),
    ];
    sortReeIndexEntries(entries);

    expect(entries[0]?.subjectDigest).toBe("sha256:bbb");
  });
});
