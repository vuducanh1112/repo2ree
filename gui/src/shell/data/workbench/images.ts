import type { WorkbenchImageCatalog } from "@core/workbench/WorkbenchImage";
import type { WorkbenchImageCatalog as WorkbenchImageCatalogWire } from "@shell/infra/api/apiTypes";
import { useQuery } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

function mapCatalog(wire: WorkbenchImageCatalogWire): WorkbenchImageCatalog {
  return { images: wire.images, defaultId: wire.default_id };
}

// The backend's workbench image catalog. It's effectively static for a session,
// so cache it indefinitely and share it across the provisioning selector and the
// bench console.
export function useWorkbenchImageCatalog() {
  const { reeApi } = useApiRuntime();
  return useQuery({
    queryKey: queryKeys.workbenchImages(),
    queryFn: async () => mapCatalog(await reeApi.listWorkbenchImages()),
    staleTime: Number.POSITIVE_INFINITY,
  });
}

// The ref of the catalog's default image — what the workbench provisions from
// when a request omits an image.
export function defaultImageRef(catalog: WorkbenchImageCatalog | undefined): string | undefined {
  if (!catalog) {
    return undefined;
  }
  return (
    catalog.images.find((image) => image.id === catalog.defaultId)?.ref ?? catalog.images[0]?.ref
  );
}
