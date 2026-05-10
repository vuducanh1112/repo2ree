import {
  createEmptyReeCatalogMetadata,
  type ReeCatalogMetadata,
  type ReeContributor,
  type ReeSpec,
} from "./ReeSpec";

type ContributorChangeResult =
  | { ok: true; spec: ReeSpec; contributor: ReeContributor }
  | { ok: false; error: string };

function metadataOf(spec: ReeSpec): ReeCatalogMetadata {
  return spec.catalog_metadata ?? createEmptyReeCatalogMetadata();
}

function withCatalogMetadata(spec: ReeSpec, catalogMetadata: ReeCatalogMetadata): ReeSpec {
  return {
    ...spec,
    catalog_metadata: catalogMetadata,
  };
}

export function patchCatalogMetadata(
  spec: ReeSpec,
  patch: Partial<Pick<ReeCatalogMetadata, "description" | "version" | "website">>,
): ReeSpec {
  return withCatalogMetadata(spec, {
    ...metadataOf(spec),
    ...patch,
  });
}

function normalizeKeyword(raw: string): string {
  return raw.trim().toLowerCase();
}

export function addCatalogKeyword(spec: ReeSpec, raw: string): ReeSpec {
  const metadata = metadataOf(spec);
  const keyword = normalizeKeyword(raw);
  if (!keyword || metadata.keywords.includes(keyword)) return spec;
  return withCatalogMetadata(spec, {
    ...metadata,
    keywords: [...metadata.keywords, keyword],
  });
}

export function removeCatalogKeyword(spec: ReeSpec, keyword: string): ReeSpec {
  const metadata = metadataOf(spec);
  return withCatalogMetadata(spec, {
    ...metadata,
    keywords: metadata.keywords.filter((item) => item !== keyword),
  });
}

function normalizeContributor(contributor: ReeContributor): ReeContributor {
  return {
    identifier: contributor.identifier.trim(),
    name: contributor.name.trim(),
    affiliation_name: contributor.affiliation_name.trim(),
    affiliation_identifier: contributor.affiliation_identifier.trim(),
  };
}

function validateContributor(
  metadata: ReeCatalogMetadata,
  contributor: ReeContributor,
  previousIdentifier?: string,
): string | null {
  if (!contributor.name) return "Name is required to add a contributor.";
  if (!contributor.identifier) return "Identifier is required to add a contributor.";
  if (
    metadata.contributors.some(
      (item) =>
        item.identifier === contributor.identifier && item.identifier !== previousIdentifier,
    )
  ) {
    return "A contributor with this identifier already exists.";
  }
  return null;
}

export function addCatalogContributor(
  spec: ReeSpec,
  draft: ReeContributor,
): ContributorChangeResult {
  const metadata = metadataOf(spec);
  const contributor = normalizeContributor(draft);
  const error = validateContributor(metadata, contributor);
  if (error) return { ok: false, error };

  return {
    ok: true,
    contributor,
    spec: withCatalogMetadata(spec, {
      ...metadata,
      contributors: [...metadata.contributors, contributor],
      corresponding_author_identifier:
        metadata.corresponding_author_identifier || contributor.identifier,
    }),
  };
}

export function updateCatalogContributor(
  spec: ReeSpec,
  previousIdentifier: string,
  draft: ReeContributor,
): ContributorChangeResult {
  const metadata = metadataOf(spec);
  const contributor = normalizeContributor(draft);
  const error = validateContributor(metadata, contributor, previousIdentifier);
  if (error) return { ok: false, error };

  return {
    ok: true,
    contributor,
    spec: withCatalogMetadata(spec, {
      ...metadata,
      contributors: metadata.contributors.map((item) =>
        item.identifier === previousIdentifier ? contributor : item,
      ),
      corresponding_author_identifier:
        metadata.corresponding_author_identifier === previousIdentifier
          ? contributor.identifier
          : metadata.corresponding_author_identifier,
    }),
  };
}

export function removeCatalogContributor(spec: ReeSpec, identifier: string): ReeSpec {
  const metadata = metadataOf(spec);
  const contributors = metadata.contributors.filter((item) => item.identifier !== identifier);
  return withCatalogMetadata(spec, {
    ...metadata,
    contributors,
    corresponding_author_identifier:
      metadata.corresponding_author_identifier === identifier
        ? contributors[0]?.identifier || null
        : metadata.corresponding_author_identifier,
  });
}

export function setCorrespondingCatalogContributor(spec: ReeSpec, identifier: string): ReeSpec {
  const metadata = metadataOf(spec);
  if (!metadata.contributors.some((item) => item.identifier === identifier)) return spec;
  return withCatalogMetadata(spec, {
    ...metadata,
    corresponding_author_identifier: identifier,
  });
}
