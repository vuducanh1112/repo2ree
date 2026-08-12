import { PAGE } from "@core/app-shell/pages";
import type { WorkbenchImage } from "@core/workbench/WorkbenchImage";
import { Input } from "@shell/ui/shared/components/FormControl";
import { Ic } from "@shell/ui/shared/components/Icon";
import { stageTone } from "@shell/ui/theme/appearance";
import type React from "react";
import styles from "./WorkbenchPage.module.css";

// The workbench owns the build stage's hue across this page (header icon,
// section accents, summary glyphs) so it reads as one coherent stage rather
// than a generic form. It is the same tone the runtime it provisions carries.
export const WORKBENCH_COLOR = stageTone(PAGE.BUILD);

// ── Image selection ────────────────────────────────────────────────────────
// The base image is chosen at provision time from the backend's image catalog
// (GET /workbench/images) or a custom reference. The catalog is the single
// source of truth — nothing here hardcodes an image ref.

// Reserved selection id for "provide your own reference"; never a catalog id.
const CUSTOM_IMAGE_ID = "custom";

export interface WorkbenchImageSelection {
  // A catalog image id, CUSTOM_IMAGE_ID, or "" to mean "use the catalog default".
  selectedId: string;
  customRef: string;
}

export const DEFAULT_WORKBENCH_IMAGE_SELECTION: WorkbenchImageSelection = {
  selectedId: "",
  customRef: "",
};

// Resolve a selection to the image ref to send to the backend. Undefined means
// "let the backend use its default": nothing picked yet, or custom selected but
// blank.
export function resolveWorkbenchImage(
  selection: WorkbenchImageSelection,
  images: readonly WorkbenchImage[],
): string | undefined {
  if (selection.selectedId === CUSTOM_IMAGE_ID) {
    return selection.customRef.trim() || undefined;
  }
  return images.find((image) => image.id === selection.selectedId)?.ref;
}

export function WorkbenchImageSelector({
  images,
  defaultId,
  selection,
  onChange,
  disabled = false,
}: {
  images: readonly WorkbenchImage[];
  defaultId: string;
  selection: WorkbenchImageSelection;
  onChange: (next: WorkbenchImageSelection) => void;
  disabled?: boolean;
}) {
  // Before the user picks anything, the catalog default reads as selected.
  const activeId = selection.selectedId || defaultId;
  return (
    <div className={styles.options}>
      {images.map((image) => (
        <div key={image.id} className={styles.imageChoice}>
          <LocationOption
            selected={activeId === image.id}
            icon={Ic.layers(16)}
            label={image.label}
            description={image.description}
            onSelect={() => !disabled && onChange({ ...selection, selectedId: image.id })}
          />
          <span className={styles.imageRef}>{image.ref}</span>
        </div>
      ))}
      <LocationOption
        selected={activeId === CUSTOM_IMAGE_ID}
        icon={Ic.layers(16)}
        label="Custom…"
        description="Provision from a specific image reference."
        onSelect={() => !disabled && onChange({ ...selection, selectedId: CUSTOM_IMAGE_ID })}
      />
      {activeId === CUSTOM_IMAGE_ID && (
        <Input
          type="text"
          aria-label="Custom image reference"
          value={selection.customRef}
          onChange={(e) => onChange({ ...selection, customRef: e.target.value })}
          placeholder="e.g. docker.io/library/docker:29-dind"
          disabled={disabled}
          flavor="code"
        />
      )}
    </div>
  );
}

interface LocationOptionProps {
  selected: boolean;
  icon: React.ReactNode;
  label: string;
  description: string;
  onSelect: () => void;
}

function LocationOption({ selected, icon, label, description, onSelect }: LocationOptionProps) {
  return (
    <button type="button" onClick={onSelect} aria-pressed={selected} className={styles.option}>
      <div aria-hidden className={styles.optionIcon}>
        {icon}
      </div>
      <div className={styles.optionBody}>
        <div className={styles.optionLabel}>{label}</div>
        <div className={styles.optionHint}>{description}</div>
      </div>
      <div aria-hidden className={styles.optionMarker} />
    </button>
  );
}
