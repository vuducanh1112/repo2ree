// A lab location represented by a workbench service dialed into the control plane.
// Pure domain shape; the data layer maps the API wire shape onto this. A lab is listed only while it holds its
// outbound connection, so `status` is "connected" for everything the fleet view
// receives — the field exists so a later broker step can add drained/draining.
export type LabStatus = "connected";

export interface Lab {
  id: string;
  label: string;
  description: string;
  lifecycleMode: "provider_managed" | "externally_managed";
  /** The curated base images this lab offers. Empty for a pre-provisioned lab. */
  images: WorkbenchImage[];
  /** Whether this lab will run a ref it did not publish. */
  acceptsCustomImage: boolean;
  status: LabStatus;
  available: boolean;
  connectedComponent?: {
    kind: "provider" | "workbench";
    build: { version?: string; revision?: string };
  };
}

// One base image a lab offers. `ref` is the only field provisioning uses; the
// rest names the entry in the picker.
export interface WorkbenchImage {
  id: string;
  ref: string;
  label: string;
  description: string;
}

// Stable display order: by label, then id. Pure; returns a new array.
export function sortLabs(labs: readonly Lab[]): Lab[] {
  return [...labs].sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
}
