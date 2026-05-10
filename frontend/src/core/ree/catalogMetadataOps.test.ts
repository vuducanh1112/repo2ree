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

    expect(duplicate.catalog_metadata.keywords).toEqual(["reproducibility"]);
  });

  it("adds contributors and sets the first as corresponding author", () => {
    const result = addCatalogContributor(createEmptyReeSpec(), {
      identifier: " https://orcid.org/0000-0000-0000-0001 ",
      name: " Ada Lovelace ",
      affiliation_name: " Analytical Engines Lab ",
      affiliation_identifier: "",
    });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.spec.catalog_metadata.contributors[0]).toMatchObject({
      identifier: "https://orcid.org/0000-0000-0000-0001",
      name: "Ada Lovelace",
      affiliation_name: "Analytical Engines Lab",
    });
    expect(result.spec.catalog_metadata.corresponding_author_identifier).toBe(
      "https://orcid.org/0000-0000-0000-0001",
    );
  });

  it("keeps corresponding author valid when contributors are edited or removed", () => {
    const first = addCatalogContributor(createEmptyReeSpec(), {
      identifier: "ada",
      name: "Ada",
      affiliation_name: "",
      affiliation_identifier: "",
    });
    if (!first.ok) throw new Error(first.error);

    const second = addCatalogContributor(first.spec, {
      identifier: "grace",
      name: "Grace",
      affiliation_name: "",
      affiliation_identifier: "",
    });
    if (!second.ok) throw new Error(second.error);

    const updated = updateCatalogContributor(second.spec, "ada", {
      identifier: "ada-new",
      name: "Ada",
      affiliation_name: "",
      affiliation_identifier: "",
    });
    if (!updated.ok) throw new Error(updated.error);

    expect(updated.spec.catalog_metadata.corresponding_author_identifier).toBe("ada-new");
    expect(
      removeCatalogContributor(updated.spec, "ada-new").catalog_metadata
        .corresponding_author_identifier,
    ).toBe("grace");
  });
});
