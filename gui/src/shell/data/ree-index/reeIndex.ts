import type { ArchiveBinding, ReeIndexEntry } from "@core/ree-index/ReeIndexEntry";
import { sortReeIndexEntries } from "@core/ree-index/ReeIndexEntry";
import type { ReeIndexEntryWire } from "@shell/infra/api/apiTypes";
import { useQuery } from "@tanstack/react-query";
import { useApiServices } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

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

export function useReeIndex(options: { depositedOnly?: boolean } = {}) {
  const { reeApi } = useApiServices();
  const depositedOnly = options.depositedOnly ?? false;
  return useQuery({
    queryKey: queryKeys.reeIndex(depositedOnly),
    queryFn: async (): Promise<ReeIndexEntry[]> => {
      const wire = await reeApi.listReeIndex({ depositedOnly });
      return sortReeIndexEntries(wire.items.map(mapEntry));
    },
  });
}
