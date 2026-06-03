import type React from "react";
import { Ic } from "../../../shared/components/Icon";
import { lgBackgrounds, lgColors, lgStatusBadge, lgStyles } from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";

// The workbench owns the cyan hue across this page (header icon, section
// accents, summary glyphs) so it reads as one coherent stage rather than a
// generic form.
export const WORKBENCH_COLOR = lgColors.cyan;

interface WorkbenchImage {
  ref: string;
  label: string;
  description: string;
}

// The base image the workbench container is built from. The backend pins a
// single image today (WORKBENCH_IMAGE = repo2ree-workbench:latest). The image
// is itself part of reproducibility, so it's versioned — see ARCHITECTURE.md
// ("The workbench image").
export const STANDARD_IMAGE: WorkbenchImage = {
  ref: "repo2ree-workbench:latest",
  label: "Standard",
  description: "Default workbench toolchain. The only image today.",
};

// Doc-grounded facts about the workbench model (COMPONENTS.md "Always
// isolated, location configurable"; ARCHITECTURE.md). Kept accurate on purpose
// — these are guarantees, not marketing.
const WORKBENCH_NOTES: { icon: React.ReactNode; text: React.ReactNode }[] = [
  {
    icon: Ic.shield(14),
    text: "Always isolated. Every REE is built inside a workbench — there is no run-on-host mode.",
  },
  {
    icon: Ic.globe(14),
    text: "Location is the only knob. Isolation is fixed; you choose where the docker endpoint runs.",
  },
  {
    icon: Ic.refresh(14),
    text: "Persistent and reusable. The workbench stays up between steps, so iteration stays fast.",
  },
  {
    icon: Ic.lock(14),
    text: "Reprovision keeps your /ree volume — the container is replaced, your edits survive.",
  },
];

export function InfoNotePanel() {
  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <span style={{ color: WORKBENCH_COLOR, display: "flex" }}>{Ic.info(22)}</span>
        <h2 style={{ margin: 0, fontSize: 15, color: lgColors.text }}>Good to know</h2>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {WORKBENCH_NOTES.map((note, i) => (
          <div
            // biome-ignore lint/suspicious/noArrayIndexKey: static, never reordered
            key={i}
            style={{ display: "flex", gap: 9, alignItems: "flex-start" }}
          >
            <span style={{ color: WORKBENCH_COLOR, display: "flex", marginTop: 1, flexShrink: 0 }}>
              {note.icon}
            </span>
            <span style={{ fontSize: 12, color: lgColors.textMid, lineHeight: 1.45 }}>
              {note.text}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

// A single fixed image today, so this is a read-only card rather than a
// selector. When the backend grows more bases this becomes a radio list again.
export function ImageCard({ image }: { image: WorkbenchImage }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "12px 14px",
        borderRadius: 9,
        border: "1.5px solid rgba(14, 165, 233, 0.58)",
        background: "rgba(239, 246, 255, 0.94)",
        boxShadow: "0 8px 20px rgba(14, 165, 233, 0.12)",
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
          color: lgColors.primaryDeep,
          background: lgBackgrounds.primary,
          border: "1px solid rgba(14, 165, 233, 0.35)",
          flexShrink: 0,
        }}
      >
        {Ic.layers(16)}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: lgColors.primaryDeep }}>
            {image.label}
          </span>
          <span style={lgStatusBadge(true)}>Default</span>
        </div>
        <div style={{ fontSize: 12, color: lgColors.textMuted, marginTop: 1 }}>
          {image.description}
        </div>
        <div style={{ fontSize: 11, color: lgColors.textMuted, fontFamily: F.mono, marginTop: 4 }}>
          {image.ref}
        </div>
      </div>
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

export function LocationOption({
  selected,
  icon,
  label,
  description,
  onSelect,
}: LocationOptionProps) {
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

export function DetailRow({
  label,
  value,
  children,
}: {
  label: string;
  value?: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "9px 12px",
        borderRadius: 8,
        background: lgBackgrounds.row,
        border: "1px solid rgba(148, 163, 184, 0.3)",
      }}
    >
      <span
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: lgColors.textMuted,
          fontFamily: F.mono,
          minWidth: 72,
          flexShrink: 0,
          textTransform: "uppercase",
          letterSpacing: 0.5,
        }}
      >
        {label}
      </span>
      {children ?? <span style={{ fontSize: 13, color: lgColors.text }}>{value}</span>}
    </div>
  );
}
