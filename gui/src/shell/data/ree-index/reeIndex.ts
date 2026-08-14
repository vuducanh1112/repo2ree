import type { ArchiveBinding, ReeIndexEntry } from "@core/ree-index/ReeIndexEntry";
import { sortReeIndexEntries } from "@core/ree-index/ReeIndexEntry";
import type { ReeIndexEntryWire } from "@shell/infra/api/apiTypes";
import { useQuery } from "@tanstack/react-query";
import { useApiServices } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

// Pure wire shape → domain map. The wire nests the descriptive fields under
// catalog_metadata (that is their shape in the sealed manifest); the view wants
// them flat, and flattening here keeps the domain model free of the manifest's
// layout.
function mapEntry(wire: ReeIndexEntryWire): ReeIndexEntry {
  return {
    subjectDigest: wire.subject_digest,
    name: wire.name,
    sealedAt: wire.sealed_at,
    description: wire.catalog_metadata?.description ?? "",
    keywords: wire.catalog_metadata?.keywords ?? [],
    reeVersion: wire.ree_version ?? "",
    archiveBindings: (wire.archive_attestations ?? []).map(mapBinding),
  };
}

function mapBinding(
  wire: NonNullable<ReeIndexEntryWire["archive_attestations"]>[number],
): ArchiveBinding {
  return {
    archive: wire.archive,
    identifier: wire.identifier,
    recordUrl: wire.record_url ?? "",
    conceptIdentifier: wire.concept_identifier ?? "",
    version: wire.version ?? "",
    signedAt: wire.signed_at ?? "",
  };
}

// Unlike the agent fleet, the index does not drift on its own: an entry appears
// when someone seals or deposits, both of which are deliberate acts taken from
// this UI. So no polling — refetching on focus is enough to pick up a seal made
// in another tab.
export function useReeIndex(options: { depositedOnly?: boolean } = {}) {
  const { reeApi } = useApiServices();
  const depositedOnly = options.depositedOnly ?? false;
  return useQuery({
    queryKey: queryKeys.reeIndex(depositedOnly),
    queryFn: async (): Promise<ReeIndexEntry[]> => {
      const wire = await reeApi.listReeIndex({ depositedOnly });
      // The route already orders newest first; sorting again makes the view's
      // order a property of the view rather than of whoever answered it.
      return sortReeIndexEntries(wire.items.map(mapEntry));
    },
  });
}
