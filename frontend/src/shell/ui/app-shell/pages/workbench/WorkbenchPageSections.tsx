import type { WorkbenchImage } from "@core/workbench/WorkbenchImage";
import { Ic } from "@shell/ui/shared/components/Icon";
import { lgBackgrounds, lgColors, lgInput } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import type React from "react";

// The workbench owns the cyan hue across this page (header icon, section
// accents, summary glyphs) so it reads as one coherent stage rather than a
// generic form.
export const WORKBENCH_COLOR = lgColors.cyan;

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
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {images.map((image) => (
        <div key={image.id} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <LocationOption
            selected={activeId === image.id}
            icon={Ic.layers(16)}
            label={image.label}
            description={image.description}
            onSelect={() => !disabled && onChange({ ...selection, selectedId: image.id })}
          />
          <span
            style={{
              fontFamily: F.mono,
              fontSize: 11.5,
              color: lgColors.textMuted,
              paddingLeft: 4,
              wordBreak: "break-all",
            }}
          >
            {image.ref}
          </span>
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
        <input
          type="text"
          value={selection.customRef}
          onChange={(e) => onChange({ ...selection, customRef: e.target.value })}
          placeholder="e.g. docker.io/org/repo2ree-workbench:edge"
          disabled={disabled}
          style={{ ...lgInput(disabled), fontFamily: F.mono, fontSize: 12 }}
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
    <button
      type="button"
      onClick={onSelect}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "12px 14px",
        borderRadius: 9,
        border: selected
          ? "1.5px solid rgba(14, 165, 233, 0.58)"
          : "1.5px solid rgba(125, 211, 252, 0.38)",
        background: selected ? "rgba(239, 246, 255, 0.94)" : lgBackgrounds.glassStrong,
        cursor: "pointer",
        textAlign: "left",
        transition: "all 0.14s",
        boxShadow: selected ? "0 8px 20px rgba(14, 165, 233, 0.12)" : "none",
        fontFamily: F.sans,
      }}
    >
      <div
        style={{
          width: 34,
          height: 34,
          borderRadius: 9,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: selected ? lgColors.primaryDeep : lgColors.textMid,
          background: selected ? lgBackgrounds.primary : lgBackgrounds.iconSoft,
          border: selected
            ? "1px solid rgba(14, 165, 233, 0.35)"
            : "1px solid rgba(125, 211, 252, 0.38)",
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: 14,
            fontWeight: selected ? 700 : 500,
            color: selected ? lgColors.primaryDeep : lgColors.text,
          }}
        >
          {label}
        </div>
        <div style={{ fontSize: 12, color: lgColors.textMuted, marginTop: 1 }}>{description}</div>
      </div>
      <div
        style={{
          width: 16,
          height: 16,
          borderRadius: "50%",
          border: `2px solid ${selected ? lgColors.blue : "rgba(148, 163, 184, 0.5)"}`,
          background: selected ? lgColors.blue : "transparent",
          flexShrink: 0,
          boxShadow: selected ? `0 0 8px ${lgColors.blue}66` : "none",
          transition: "all 0.14s",
        }}
      />
    </button>
  );
}
