import type { DraftManifest } from "@core/workspace/WorkspaceTypes";
import { type CSSProperties, useMemo, useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { lgColors } from "../../theme/lightGlassTheme";
import { C, F } from "../../theme/theme";
import { HudConsole } from "./HudConsole";

interface ReeStateConsoleProps {
  draftManifest?: DraftManifest;
}

interface FileInventory {
  workspace?: unknown[];
  overlay?: unknown[];
  artifacts?: unknown[];
}

const HUD_RIGHT = 16;
const HUD_TOP = 16;
const HUD_WIDTH_OPEN = 360;
const HUD_WIDTH_COLLAPSED = 224;

export function ReeStateConsole({ draftManifest }: ReeStateConsoleProps) {
  const [open, setOpen] = useState(false);
  const [jsonOpen, setJsonOpen] = useState(false);
  const summary = useMemo(() => summarizeDraftManifest(draftManifest), [draftManifest]);
  const manifestJson = useMemo(
    () => (draftManifest ? `${JSON.stringify(draftManifest, null, 2)}\n` : ""),
    [draftManifest],
  );

  return (
    <HudConsole
      open={open}
      onToggle={() => setOpen((value) => !value)}
      widthOpen={HUD_WIDTH_OPEN}
      widthCollapsed={HUD_WIDTH_COLLAPSED}
      outerStyle={{
        right: HUD_RIGHT,
        top: HUD_TOP,
        maxHeight: "calc(100% - 32px)",
      }}
      icon={Ic.info(16)}
      iconColor={lgColors.textMuted}
      title="REE State"
      on={Boolean(draftManifest)}
      expandLabel="Expand REE state"
      collapseLabel="Collapse REE state"
      bodyMaxHeight={560}
      bodyStyle={{ gap: 9 }}
    >
      <div style={gridStyle}>
        <Fact label="Workspace" value={`${summary.workspaceCount} files`} />
        <Fact label="Overlay" value={`${summary.overlayCount} files`} />
        <Fact label="Artifacts" value={`${summary.artifactCount} files`} />
        <Fact label="Runtime" value={summary.runtime} wide />
        <Fact label="Source" value={summary.source} wide />
        <Fact label="Experiments" value={String(summary.experimentCount)} />
        <Fact label="Seal" value={summary.seal} />
      </div>

      <button type="button" onClick={() => setJsonOpen((value) => !value)} style={toggleButton}>
        {jsonOpen ? Ic.chevD(13) : Ic.chevR(13)}
        <span>Projection JSON</span>
      </button>

      {jsonOpen && (
        <pre
          style={{
            margin: 0,
            maxHeight: 260,
            overflow: "auto",
            padding: 10,
            borderRadius: 8,
            border: `1px solid ${C.border}`,
            background: "#0d1117",
            color: "#dbeafe",
            fontFamily: F.mono,
            fontSize: 10.5,
            lineHeight: 1.55,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {manifestJson || "{}\n"}
        </pre>
      )}
    </HudConsole>
  );
}

function summarizeDraftManifest(draftManifest: DraftManifest | undefined) {
  if (!draftManifest) {
    return {
      workspaceCount: 0,
      overlayCount: 0,
      artifactCount: 0,
      runtime: "not declared",
      source: "not acquired",
      experimentCount: 0,
      seal: "unsealed",
    };
  }

  const inventory = asRecord(draftManifest.file_inventory) as FileInventory;
  const workspaceCount = Array.isArray(inventory.workspace) ? inventory.workspace.length : 0;
  const overlayCount = Array.isArray(inventory.overlay) ? inventory.overlay.length : 0;
  const artifactCount = Array.isArray(inventory.artifacts) ? inventory.artifacts.length : 0;
  const experiments = Array.isArray(draftManifest.experiments) ? draftManifest.experiments : [];
  const source =
    stringValue(draftManifest.origin_url) ||
    stringValue(draftManifest.source_acquired_by) ||
    (draftManifest.source_available ? "available" : "not acquired");
  const runtime = stringValue(draftManifest.runtime) || "not declared";
  const sealHash = stringValue(draftManifest.seal_hash);

  return {
    workspaceCount,
    overlayCount,
    artifactCount,
    runtime,
    source,
    experimentCount: experiments.length,
    seal: sealHash ? "sealed" : "unsealed",
  };
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function stringValue(value: unknown): string {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function Fact({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div
      style={{
        gridColumn: wide ? "1 / -1" : undefined,
        minWidth: 0,
        padding: "8px 10px",
        borderRadius: 8,
        border: `1px solid ${C.border}`,
        background: C.surfaceAlt,
      }}
    >
      <div
        style={{
          color: C.textMuted,
          fontFamily: F.mono,
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: 0.5,
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
      <div
        title={value}
        style={{
          marginTop: 3,
          color: C.text,
          fontFamily: F.sans,
          fontSize: 12,
          fontWeight: 600,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {value}
      </div>
    </div>
  );
}

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
  gap: 7,
};

const toggleButton: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 6,
  width: "100%",
  border: `1px solid ${C.border}`,
  borderRadius: 8,
  background: "transparent",
  color: C.textMid,
  cursor: "pointer",
  padding: "8px 10px",
  fontFamily: F.sans,
  fontSize: 12,
  fontWeight: 600,
};
