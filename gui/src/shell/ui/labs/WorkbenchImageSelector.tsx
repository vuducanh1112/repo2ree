import { activeImageId, type WorkbenchImageSelection } from "@core/lab/imageSelection";
import type { WorkbenchImage } from "@core/lab/Lab";
import { Ic } from "@shell/ui/shared/components/Icon";
import type React from "react";
import styles from "./WorkbenchImageSelector.module.css";

// The image a new REE declares is chosen from the ones its lab offers. The lab is
// the single source of truth — nothing here hardcodes an image ref.

export function WorkbenchImageSelector({
  images,
  selection,
  onChange,
  disabled = false,
}: {
  images: readonly WorkbenchImage[];
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
            onSelect={() => !disabled && onChange({ selectedId: image.id })}
          />
          {/* The ref is shown, not summarised: it is the base of everything
              this REE will later claim to reproduce. An entry named by its ref
              already shows it. */}
          {image.label !== image.ref && <span className={styles.imageRef}>{image.ref}</span>}
        </div>
      ))}
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
