// A base image offered for workbench provisioning. Domain shape used by the UI;
// the data layer maps the API DTO onto this.
export interface WorkbenchImage {
  id: string;
  ref: string;
  label: string;
  description: string;
}

export interface WorkbenchImageCatalog {
  images: WorkbenchImage[];
  /** Id of the image used when a provisioning request omits one. */
  defaultId: string;
}
