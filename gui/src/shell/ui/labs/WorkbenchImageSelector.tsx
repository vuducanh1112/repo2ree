import {
  activeImageId,
  CUSTOM_IMAGE_ID,
  type WorkbenchImageSelection,
} from "@core/lab/imageSelection";
import type { WorkbenchImage } from "@core/lab/Lab";
import { Input } from "@shell/ui/shared/components/FormControl";
import { Ic } from "@shell/ui/shared/components/Icon";
import type React from "react";
import styles from "./WorkbenchImageSelector.module.css";

// The base image is chosen at provision time from the lab's own catalog or, at
// a lab that accepts one, a reference the author supplies. The catalog is the
// single source of truth — nothing here hardcodes an image ref.

export function WorkbenchImageSelector({
  images,
  acceptsCustomImage,
  selection,
  onChange,
  disabled = false,
}: {
  images: readonly WorkbenchImage[];
  acceptsCustomImage: boolean;
  selection: WorkbenchImageSelection;
  onChange: (next: WorkbenchImageSelection) => void;
  disabled?: boolean;
}) {
  const activeId = activeImageId(selection, images);
  return (
    <div className={styles.options}>
      {images.map((image) => (
        <div key={image.id} className={styles.imageChoice}>
          <ImageOption
            selected={activeId === image.id}
            icon={Ic.layers(16)}
            label={image.label}
            description={image.description}
            onSelect={() => !disabled && onChange({ ...selection, selectedId: image.id })}
          />
          {/* The ref is shown, not summarised: it is the base of everything
              this REE will later claim to reproduce. */}
          <span className={styles.imageRef}>{image.ref}</span>
        </div>
      ))}
      {acceptsCustomImage && (
        <ImageOption
          selected={activeId === CUSTOM_IMAGE_ID}
          icon={Ic.layers(16)}
          label="Custom…"
          description="Provision from a specific image reference."
          onSelect={() => !disabled && onChange({ ...selection, selectedId: CUSTOM_IMAGE_ID })}
        />
      )}
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

interface ImageOptionProps {
  selected: boolean;
  icon: React.ReactNode;
  label: string;
  description: string;
  onSelect: () => void;
}

function ImageOption({ selected, icon, label, description, onSelect }: ImageOptionProps) {
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
