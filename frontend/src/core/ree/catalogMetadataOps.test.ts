import { describe, expect, it } from "vitest";
import {
  addCatalogContributor,
  addCatalogKeyword,
  removeCatalogContributor,
  updateCatalogContributor,
} from "./catalogMetadataOps";
import { createEmptyReeSpec } from "./ReeSpec";

describe("catalog metadata operations", () => {
  it("normalizes and deduplicates keywords", () => {
    const spec = addCatalogKeyword(createEmptyReeSpec(), " Reproducibility ");
    const duplicate = addCatalogKeyword(spec, "reproducibility");

    expect(duplicate.catalogMetadata.keywords).toEqual(["reproducibility"]);
  });

  it("adds contributors and sets the first as corresponding author", () => {
    const result = addCatalogContributor(createEmptyReeSpec(), {
      identifier: " https://orcid.org/0000-0000-0000-0001 ",
      name: " Ada Lovelace ",
      affiliationName: " Analytical Engines Lab ",
      affiliationIdentifier: "",
    });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.spec.catalogMetadata.contributors[0]).toMatchObject({
      identifier: "https://orcid.org/0000-0000-0000-0001",
      name: "Ada Lovelace",
      affiliationName: "Analytical Engines Lab",
    });
    expect(result.spec.catalogMetadata.correspondingAuthorIdentifier).toBe(
      "https://orcid.org/0000-0000-0000-0001",
    );
  });

  it("keeps corresponding author valid when contributors are edited or removed", () => {
    const first = addCatalogContributor(createEmptyReeSpec(), {
      identifier: "ada",
      name: "Ada",
      affiliationName: "",
      affiliationIdentifier: "",
    });
    if (!first.ok) throw new Error(first.error);

    const second = addCatalogContributor(first.spec, {
      identifier: "grace",
      name: "Grace",
      affiliationName: "",
      affiliationIdentifier: "",
    });
    if (!second.ok) throw new Error(second.error);

    const updated = updateCatalogContributor(second.spec, "ada", {
      identifier: "ada-new",
      name: "Ada",
      affiliationName: "",
      affiliationIdentifier: "",
    });
    if (!updated.ok) throw new Error(updated.error);

    expect(updated.spec.catalogMetadata.correspondingAuthorIdentifier).toBe("ada-new");
    expect(
      removeCatalogContributor(updated.spec, "ada-new").catalogMetadata
        .correspondingAuthorIdentifier,
    ).toBe("grace");
  });
});
