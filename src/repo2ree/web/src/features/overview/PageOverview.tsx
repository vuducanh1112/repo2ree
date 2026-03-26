import React, { useEffect, useRef } from "react";
import { Ic } from "../../components/Icon";
import { Toggle } from "../../components/Toggle";
import { FIELD_META } from "../../constants/fieldMeta";
import { LEVELS } from "../../constants/levels";
import { PAGE } from "../../constants/pages";
import { SERVICES } from "../../constants/services";
import {
  C,
  F,
  hoverBg,
  hoverBorderColor,
  hoverBrightness,
  S_ACTION_BUTTON_BASE,
  S_FLEX_ROW_CENTER_GAP_6,
  S_OVERVIEW_META_FOOTER,
  S_OVERVIEW_PANEL_BADGE_BASE,
  S_OVERVIEW_PANEL_BUTTON_BASE,
  S_OVERVIEW_PANEL_FIELDS,
  S_OVERVIEW_PANEL_FOOTER,
  S_OVERVIEW_PANEL_HEADER_ROW,
  S_OVERVIEW_PANEL_INCLUDE_LABEL_BASE,
  S_OVERVIEW_PANEL_STATUS_ROW_BASE,
  S_OVERVIEW_SEAL_STATUS_BADGE_BASE,
  S_OVERVIEW_SEALED_ACTION_BTN_BASE,
  S_OVERVIEW_SEALED_META_KEY,
  S_OVERVIEW_SEALED_META_ROW,
  S_PANEL_HEADER_LABEL,
  S_SECTION_LABEL,
} from "../../constants/theme";
import type { Badges, FileTreeNode, Ree, Timestamps } from "../../types";
import { findVirtualFileByName, listTreeFiles } from "../../utils";
import { fmtBytes } from "../../utils/formatting";
import { PanelCableOverlay } from "./PanelCableOverlay";
import { PodWidget } from "./PodWidget";

interface PanelFieldRowProps {
  label: string;
  value: string | null | undefined;
  emptyText?: string;
  filled: boolean;
  dotColor: string;
  dotGlow: string;
  labelColor: string;
  labelBg: string;
  labelBorderColor: string;
  onClick?: () => void;
  isLast?: boolean;
}
function PanelFieldRow({
  label,
  value,
  emptyText = "not set",
  filled,
  dotColor,
  dotGlow,
  labelColor,
  labelBg,
  labelBorderColor,
  onClick,
  isLast,
}: PanelFieldRowProps) {
  const [hovered, setHovered] = React.useState(false);
  const [tooltipPos, setTooltipPos] = React.useState<{ x: number; y: number } | null>(null);
  const [isOverflowing, setIsOverflowing] = React.useState(false);
  const rowRef = React.useRef<HTMLButtonElement>(null);
  const valueRef = React.useRef<HTMLSpanElement>(null);

  const showTooltip = hovered && filled && value && isOverflowing;

  const handleMouseEnter = (mouseEvent: React.MouseEvent<HTMLButtonElement>) => {
    setHovered(true);
    const rect = mouseEvent.currentTarget.getBoundingClientRect();
    setTooltipPos({ x: rect.left, y: rect.top });
    if (valueRef.current) {
      setIsOverflowing(valueRef.current.scrollWidth > valueRef.current.offsetWidth);
    }
  };
  const handleMouseLeave = () => {
    setHovered(false);
    setTooltipPos(null);
  };

  return (
    <div
      style={{
        position: "relative",
      }}
    >
      <button
        type="button"
        ref={rowRef}
        onClick={onClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        style={{
          ...{
            display: "flex",
            alignItems: "stretch",
            width: "100%",
            textAlign: "left",
            border: "none",
            transition: "background 0.12s",
          },
          background: hovered && onClick ? C.surfaceAlt : "transparent",
          borderBottom: isLast ? "none" : `1px solid ${C.border}`,
          cursor: onClick ? "pointer" : "default",
        }}
      >
        <div
          style={{
            ...{
              display: "flex",
              alignItems: "center",
              gap: 5,
              padding: "4px 8px",
              minWidth: 80,
              maxWidth: 80,
              flexShrink: 0,
            },
            borderRight: `1px solid ${filled ? labelBorderColor : C.border}`,
            background: filled ? labelBg : "transparent",
          }}
        >
          <div
            style={{
              ...{
                width: 5,
                height: 5,
                borderRadius: "50%",
                flexShrink: 0,
              },
              background: filled ? dotColor : "#d1d5db",
              boxShadow: filled ? `0 0 5px ${dotGlow}` : "none",
            }}
          />
          <span
            style={{
              ...{
                fontSize: 10,
                fontFamily: F.sans,
                fontWeight: 600,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              },
              color: filled ? labelColor : C.textMuted,
            }}
          >
            {label}
          </span>
        </div>
        <div
          style={{
            padding: "4px 8px",
            flex: 1,
            minWidth: 0,
          }}
        >
          <span
            ref={valueRef}
            style={{
              ...{
                fontSize: 10,
                fontFamily: F.mono,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                display: "block",
              },
              color: filled ? C.textMid : C.textMuted,
              fontStyle: filled ? "normal" : "italic",
            }}
          >
            {filled ? value : emptyText}
          </span>
        </div>
      </button>
      {showTooltip && tooltipPos && (
        <div
          style={{
            ...{
              position: "fixed",
              zIndex: 9999,
              background: C.text,
              color: "#fff",
              fontFamily: F.mono,
              fontSize: 11,
              padding: "5px 9px",
              borderRadius: 6,
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              maxWidth: 320,
              boxShadow: "0 4px 16px rgba(0,0,0,0.22)",
              pointerEvents: "none",
              lineHeight: 1.5,
            },
            left: tooltipPos.x,
            top: tooltipPos.y - 34,
          }}
        >
          {value}
          <div
            style={{
              position: "absolute",
              bottom: -5,
              left: 14,
              width: 10,
              height: 10,
              background: C.text,
              transform: "rotate(45deg)",
              borderRadius: 1,
            }}
          />
        </div>
      )}
    </div>
  );
}

interface OverviewPanelFieldProps {
  label: string;
  value: string | null | undefined;
  emptyText?: string;
  filled: boolean;
  onClick?: () => void;
}

interface OverviewPanelProps {
  color: string;
  label: string;
  fields: OverviewPanelFieldProps[];
  badge?: string;
  footerLabel: string;
  onFooterClick: () => void;
  headerExtra?: React.ReactNode;
}

interface PageOverviewProps {
  ree: Ree;
  onReeChange: (ree: Ree) => void;
  level: number;
  onNavigate: (key: string) => void;
  badges?: Badges;
  timestamps?: Timestamps;
  onGoField: (key: string) => void;
  files?: FileTreeNode[];
  snapshotFiles?: FileTreeNode[];
  locked?: boolean;
  onSeal: () => void;
  onPreviewReviewer: () => void;
  onDownloadRee?: () => void;
}
export function PageOverview({
  ree,
  onReeChange,
  level,
  onNavigate,
  badges = {},
  timestamps = {},
  onGoField,
  files = [],
  snapshotFiles = [],
  locked = false,
  onSeal,
  onPreviewReviewer,
  onDownloadRee,
}: PageOverviewProps) {
  const [showSealConfirm, setShowSealConfirm] = React.useState(false);
  const levelMeta = LEVELS[Math.min(level, 7)];
  const panel = (extra: React.CSSProperties = {}): React.CSSProperties => ({
    ...{
      background: C.surface,
      border: `1px solid ${C.border}`,
      borderRadius: 8,
    },
    ...extra,
  });

  // Define OverviewPanel component here so it has access to panel()
  const OverviewPanel = React.forwardRef<HTMLDivElement, OverviewPanelProps>(
    ({ color, label, fields, badge, footerLabel, onFooterClick, headerExtra }, ref) => {
      const getLighterColor = (hex: string) => `${hex}99`;
      const getDarkerInkColor = (hex: string) => {
        const colorMap: Record<string, string> = {
          "#f59e0b": "#92400e",
          "#0891b2": "#164e63",
          "#16a34a": "#15803d",
          "#e4572e": "#9a3412",
          "#059669": "#065f46",
        };
        return colorMap[hex] || hex;
      };
      const getBackgroundColor = (hex: string) => {
        const bgMap: Record<string, string> = {
          "#f59e0b": "#fffbeb",
          "#0891b2": "#ecfeff",
          "#16a34a": "#f0fdf4",
          "#e4572e": "#fff7f5",
          "#059669": "#f0fdf4",
        };
        return bgMap[hex] || "#f5f3ff";
      };

      const dotGlow = getLighterColor(color);
      const labelColor = getDarkerInkColor(color);
      const labelBg = getBackgroundColor(color);
      const labelBorderColor = `${color}25`;

      return (
        <div ref={ref} style={panel({ overflow: "hidden" })}>
          <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
            <div
              style={{
                width: 5,
                height: 5,
                borderRadius: "50%",
                background: color,
                boxShadow: `0 0 5px ${dotGlow}`,
              }}
            />
            <span style={S_PANEL_HEADER_LABEL}>{label}</span>
            {badge && (
              <span
                style={{
                  ...S_OVERVIEW_PANEL_BADGE_BASE,
                  color,
                  background: labelBg,
                  border: `1px solid ${color}40`,
                }}
              >
                {badge}
              </span>
            )}
            {headerExtra && <div style={{ marginLeft: "auto" }}>{headerExtra}</div>}
          </div>
          <div style={S_OVERVIEW_PANEL_FIELDS}>
            {fields.map((field, idx) => (
              <PanelFieldRow
                key={field.label}
                label={field.label}
                value={field.value}
                emptyText={field.emptyText}
                filled={field.filled}
                dotColor={color}
                dotGlow={dotGlow}
                labelColor={labelColor}
                labelBg={labelBg}
                labelBorderColor={labelBorderColor}
                onClick={field.onClick}
                isLast={idx === fields.length - 1}
              />
            ))}
          </div>
          <div style={S_OVERVIEW_PANEL_FOOTER}>
            <button
              type="button"
              onClick={onFooterClick}
              style={{
                ...S_OVERVIEW_PANEL_BUTTON_BASE,
                color: labelColor,
                background: labelBg,
                border: `1px solid ${color}40`,
              }}
              {...hoverBrightness(95)}
            >
              → {footerLabel}
            </button>
          </div>
        </div>
      );
    },
  );

  // Cable overlay refs
  const cableContainerRef = useRef<HTMLDivElement>(null);
  const sourceRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<HTMLDivElement>(null);
  const leftPanelRef = useRef<HTMLDivElement>(null);
  const podColumnRef = useRef<HTMLDivElement>(null);
  const podSvgRef = useRef<SVGSVGElement>(null);

  // Responsive pod size — track center column width via ResizeObserver
  const [podSize, setPodSize] = React.useState(480);
  React.useEffect(() => {
    const el = podColumnRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width;
      // Clamp: min 260 so the pod stays readable, max 620 so it doesn't overwhelm
      setPodSize(Math.min(640, Math.max(260, w)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const swhRef = useRef<HTMLDivElement>(null);
  const evaluateRef = useRef<HTMLDivElement>(null);
  const sbomRef = useRef<HTMLDivElement>(null);
  const sealRef = useRef<HTMLDivElement>(null);
  const archiveRef = useRef<HTMLDivElement>(null);
  const activationRef = useRef<HTMLDivElement>(null);

  // Source panel state
  const sourceInWorkspace = !!ree._sourceAvailable;
  const sourceFromUpload = ree._sourceAcquiredBy === "upload" && !!ree._sourceAvailable;
  const sourceFromDownload = ree._sourceAcquiredBy === "download" && !!ree._sourceAvailable;
  const sourceProvisionStatus = sourceFromUpload
    ? "Uploaded archive"
    : sourceFromDownload
      ? "Downloaded from origin"
      : "Not provided yet";
  const sourceIncluded = sourceInWorkspace && !!ree._sourceIncluded;
  const canIncludeSource = sourceInWorkspace;
  const toggleSource = () => {
    if (!canIncludeSource) return;
    onReeChange?.({ ...ree, _sourceIncluded: !sourceIncluded });
  };

  useEffect(() => {
    if (!sourceInWorkspace && ree._sourceIncluded) {
      onReeChange?.({ ...ree, _sourceIncluded: false });
    }
  }, [sourceInWorkspace, ree, onReeChange]);

  // Runtime panel state
  const runtimeVal = ree?.runtime && ree.runtime !== "__skipped__" ? ree.runtime.trim() : "";
  const runtimeIncluded = !!ree?._runtimeIncluded;
  const canIncludeRuntime = !!runtimeVal;
  const toggleRuntime = () => {
    if (!canIncludeRuntime) return;
    onReeChange?.({ ...ree, _runtimeIncluded: !runtimeIncluded });
  };

  // Find runtime file in virtual tree and get its mock size
  const runtimeFile = runtimeVal ? findVirtualFileByName(files, runtimeVal) : null;
  // Extract mock size string if present in content, else estimate from content length
  const runtimeSizeStr = (() => {
    if (!runtimeFile) return null;
    const m = (runtimeFile.content || "").match(/Size:\s*(~?[\d.]+ ?[KMGT]?B)/i);
    if (m) return m[1];
    return fmtBytes(new TextEncoder().encode(runtimeFile.content || "").length);
  })();

  // SBOM metadata
  const sbomVal = ree?.sbom ? ree.sbom.trim() : "";
  const sbomFile = sbomVal ? findVirtualFileByName(files, sbomVal) : null;
  const sbomMeta = (() => {
    if (!sbomFile) return null;
    try {
      const parsed = JSON.parse(sbomFile.content || "{}");
      const pkgCount = Array.isArray(parsed.packages)
        ? parsed.packages.length
        : Array.isArray(parsed.components)
          ? parsed.components.length
          : null;
      const fmt = parsed.spdxVersion
        ? `SPDX ${parsed.spdxVersion.replace("SPDX-", "")}`
        : parsed.bomFormat === "CycloneDX"
          ? `CycloneDX ${parsed.specVersion || ""}`
          : parsed.descriptor?.name === "syft"
            ? "Syft JSON"
            : "JSON";
      return { pkgCount, fmt };
    } catch {
      return null;
    }
  })();

  // Compute source file stats
  const allFiles = listTreeFiles(snapshotFiles);
  const fileCount = allFiles.length;
  const totalBytes = allFiles.reduce(
    (totalSize, file) =>
      totalSize + (file.content ? new TextEncoder().encode(file.content).length : 0),
    0,
  );

  return (
    <div
      style={{
        flex: 1,
        overflowY: "auto",
        padding: 28,
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          marginBottom: 20,
          display: "flex",
          alignItems: "baseline",
          gap: 14,
        }}
      >
        <div>
          <div
            style={{
              ...S_SECTION_LABEL,
              fontSize: 10,
              fontWeight: 600,
              marginBottom: 4,
            }}
          >
            Reproducible Execution Environment
          </div>
          <div
            style={{
              fontSize: 18,
              fontWeight: 800,
              color: C.text,
              letterSpacing: 0.2,
              fontFamily: F.mono,
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            {ree.name || "untitled-env"}
            <span
              style={{
                ...{
                  fontSize: 9,
                  fontWeight: 700,
                  padding: "2px 8px",
                  borderRadius: 3,
                  letterSpacing: 1.5,
                  textTransform: "uppercase",
                },
                background: `${levelMeta.color}16`,
                color: levelMeta.color,
                border: `1px solid ${levelMeta.color}40`,
              }}
            >
              {levelMeta.label}
            </span>
          </div>
        </div>
        <div
          style={{
            flex: 1,
            height: 1,
            background: C.border,
            marginBottom: 2,
          }}
        />
        <div
          style={{
            fontSize: 9,
            fontFamily: F.mono,
            color: C.textMuted,
            letterSpacing: 1,
          }}
        >
          {new Date().toISOString().slice(0, 10)}
        </div>
      </div>

      {/* ── Three columns ── */}
      <div
        ref={cableContainerRef}
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 18,
          position: "relative",
        }}
      >
        <PanelCableOverlay
          containerRef={cableContainerRef}
          sourceRef={sourceRef}
          runtimeRef={runtimeRef}
          metadataRef={leftPanelRef}
          swhRef={swhRef}
          evaluateRef={evaluateRef}
          sbomRef={sbomRef}
          sealRef={sealRef}
          archiveRef={archiveRef}
          activationRef={activationRef}
          podSvgRef={podSvgRef}
          level={level}
          badges={badges}
          ree={ree}
        />

        {/* Left — source + fields */}
        <div
          style={{
            width: 196,
            flexShrink: 0,
            position: "relative",
            zIndex: 1,
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
          {/* Source panel */}
          <OverviewPanel
            ref={sourceRef}
            color="#f59e0b"
            label="Source"
            fields={[
              {
                label: "Origin URL",
                value: ree.origin_url || null,
                filled: !!ree.origin_url,
                onClick: () => onGoField?.("origin_url"),
              },
              {
                label: "Origin Provisioning Status",
                value: sourceProvisionStatus,
                filled: !!ree._sourceAcquiredBy,
                onClick: () => onGoField?.("_sourceAcquiredBy"),
              },
              {
                label: "Origin Type",
                value: ree.source_type || null,
                filled: !!ree.source_type,
                onClick: () => onGoField?.("source_type"),
              },
              {
                label: "Files",
                value: ree._sourceAvailable
                  ? fileCount > 0
                    ? `${fileCount} file${fileCount !== 1 ? "s" : ""} · ${fmtBytes(totalBytes)}`
                    : "downloaded"
                  : null,
                filled: !!ree._sourceAvailable,
                emptyText: "not downloaded",
                onClick: () => onNavigate?.(PAGE.SOURCE),
              },
            ]}
            footerLabel="Go to Source"
            onFooterClick={() => onNavigate?.(PAGE.SOURCE)}
            headerExtra={
              <div
                style={{
                  ...S_OVERVIEW_PANEL_STATUS_ROW_BASE,
                  opacity: canIncludeSource ? 1 : 0.45,
                }}
              >
                <span
                  style={{
                    ...S_OVERVIEW_PANEL_INCLUDE_LABEL_BASE,
                    color: sourceIncluded ? "#92400e" : C.textMuted,
                  }}
                >
                  {sourceIncluded ? "Included" : "Include"}
                </span>
                <Toggle
                  on={sourceIncluded}
                  disabled={!canIncludeSource}
                  color="#f59e0b"
                  onChange={toggleSource}
                />
              </div>
            }
          />

          {/* Metadata panel */}
          <div ref={leftPanelRef} style={panel({ overflow: "hidden" })}>
            <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
              <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#22c55e" }} />
              <span style={S_PANEL_HEADER_LABEL}>Metadata</span>
              <span
                style={{
                  marginLeft: "auto",
                  fontSize: 8,
                  fontFamily: F.mono,
                  color: C.textMuted,
                  letterSpacing: 0.5,
                }}
              >
                {
                  (["name", "hardware_description"] as (keyof Ree)[]).filter((f) =>
                    f === "hardware_description"
                      ? Object.values((ree[f] as Record<string, string>) || {}).some((v) => v)
                      : !!ree[f],
                  ).length
                }
                /2
              </span>
            </div>
            <div style={S_OVERVIEW_PANEL_FIELDS}>
              {(["name", "hardware_description"] as (keyof Ree)[]).map((f, fi) => {
                const isHw = f === "hardware_description";
                const rawVal = ree[f];
                const filled = isHw
                  ? Object.values((rawVal as Record<string, string>) || {}).some((v) => v)
                  : !!rawVal;
                const label = FIELD_META[f as string]?.label || (isHw ? "Hardware" : String(f));
                const displayVal = isHw
                  ? Object.entries((rawVal as Record<string, string>) || {})
                      .filter(([, v]) => v)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(", ")
                  : String(rawVal ?? "");
                return (
                  <PanelFieldRow
                    key={f}
                    label={label}
                    value={filled ? displayVal : null}
                    filled={filled}
                    dotColor="#22c55e"
                    dotGlow="#22c55e99"
                    labelColor="#15803d"
                    labelBg="#f0fdf4"
                    labelBorderColor="#22c55e25"
                    isLast={fi === 1}
                    onClick={() => (onGoField ? onGoField(String(f)) : undefined)}
                  />
                );
              })}
            </div>
            <div style={S_OVERVIEW_META_FOOTER}>
              <button
                type="button"
                onClick={() => onNavigate?.(PAGE.METADATA)}
                style={{
                  ...S_OVERVIEW_PANEL_BUTTON_BASE,
                  color: C.text,
                  background: "#f0fdf4",
                  border: `1px solid ${C.border}40`,
                  marginTop: 2,
                }}
                {...hoverBrightness(95)}
              >
                → Edit Metadata
              </button>
            </div>
          </div>

          {/* Runtime panel */}
          <OverviewPanel
            ref={runtimeRef}
            color="#0891b2"
            label="Runtime"
            fields={[
              {
                label: "Runtime",
                value: runtimeVal || null,
                filled: !!runtimeVal,
                emptyText: "not set",
                onClick: () => onNavigate?.(PAGE.BUILD),
              },
              ...(runtimeSizeStr
                ? [
                    {
                      label: "Size",
                      value: runtimeSizeStr,
                      filled: !!runtimeSizeStr,
                      onClick: () => onNavigate?.(PAGE.BUILD),
                    },
                  ]
                : []),
              {
                label: "Build Script",
                value: ree.build_runtime_script || null,
                filled: !!ree.build_runtime_script,
                emptyText: "not set",
                onClick: () => onGoField?.("build_runtime_script"),
              },
            ]}
            footerLabel="Go to Build Runtime"
            onFooterClick={() => onNavigate?.(PAGE.BUILD)}
            headerExtra={
              <div
                style={{
                  ...S_OVERVIEW_PANEL_STATUS_ROW_BASE,
                  opacity: canIncludeRuntime ? 1 : 0.45,
                }}
              >
                <span
                  style={{
                    ...S_OVERVIEW_PANEL_INCLUDE_LABEL_BASE,
                    color: runtimeIncluded ? "#164e63" : C.textMuted,
                  }}
                >
                  {runtimeIncluded ? "Included" : "Include"}
                </span>
                <Toggle
                  on={runtimeIncluded}
                  disabled={!canIncludeRuntime}
                  color="#0891b2"
                  onChange={toggleRuntime}
                />
              </div>
            }
          />

          {/* SBOM panel */}
          {(() => {
            const earned = !!badges?.sbom;
            const color = "#16a34a";
            const sbomFields: OverviewPanelFieldProps[] = [
              {
                label: "SBOM Path",
                value: sbomVal || null,
                filled: !!sbomVal,
                emptyText: "not set",
                onClick: () => onNavigate?.(PAGE.SBOM),
              },
            ];
            if (sbomMeta?.fmt) {
              sbomFields.push({
                label: "Format",
                value: sbomMeta.fmt,
                filled: true,
                onClick: () => onNavigate?.(PAGE.SBOM),
              });
            }
            if (sbomMeta?.pkgCount != null) {
              sbomFields.push({
                label: "Packages",
                value: `${sbomMeta.pkgCount} pkg${sbomMeta.pkgCount !== 1 ? "s" : ""}`,
                filled: true,
                onClick: () => onNavigate?.(PAGE.SBOM),
              });
            }
            return (
              <OverviewPanel
                ref={sbomRef}
                color={color}
                label="SBOM"
                badge={earned ? "OK" : undefined}
                fields={sbomFields}
                footerLabel="Generate SBOM"
                onFooterClick={() => onNavigate?.(PAGE.SBOM)}
              />
            );
          })()}
        </div>

        {/* Center — pod + artifact bar + status */}
        <div
          ref={podColumnRef}
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 12,
            minWidth: 0,
            position: "relative",
            zIndex: 1,
          }}
        >
          <PodWidget level={level} svgRef={podSvgRef} size={podSize} />

          {/* ── Seal strip ── */}
          {(() => {
            const sealed = locked && ree._sealedAt;
            const cableItems = [
              {
                key: PAGE.METADATA,
                label: "Metadata",
                live:
                  (["name", "hardware_description"] as (keyof Ree)[]).filter((f) =>
                    f === "hardware_description"
                      ? Object.values((ree[f] as Record<string, string>) || {}).some((v) => v)
                      : !!ree[f],
                  ).length > 0,
              },
              { key: PAGE.SOURCE, label: "Source", live: !!ree._sourceAvailable },
              { key: "runtime", label: "Runtime", live: !!ree._runtimeIncluded },
              { key: "swh", label: "Software Heritage", live: !!ree.swhid },
              { key: "sbom", label: "SBOM", live: !!ree.sbom },
              { key: "evaluate", label: "Evaluate", live: !!badges?.evaluate },
              {
                key: "archive",
                label: "Archival & DOIs",
                live: !!(ree.zenodo_doi || ree.dataverse_doi),
              },
              {
                key: "activation",
                label: "Test Activation",
                live: !!badges?.activation,
              },
            ];
            const liveCount = cableItems.filter((c) => c.live).length;
            const totalCables = cableItems.length;
            const allLive = liveCount === totalCables;
            const missing = cableItems.filter((c) => !c.live);
            const currentLevelMeta = LEVELS[Math.min(level, 7)];

            if (sealed) {
              const sealDate = new Date(ree._sealedAt).toLocaleString([], {
                year: "numeric",
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              });
              return (
                <div
                  ref={sealRef}
                  style={{
                    ...{
                      width: "100%",
                      maxWidth: 480,
                      background: C.surface,
                      borderRadius: 10,
                      overflow: "hidden",
                    },
                    border: `1.5px solid ${currentLevelMeta.color}50`,
                    boxShadow: `0 0 0 3px ${currentLevelMeta.color}14, 0 2px 12px rgba(0,0,0,0.07)`,
                  }}
                >
                  <div
                    style={{
                      ...{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        padding: "9px 14px",
                      },
                      borderBottom: `1px solid ${currentLevelMeta.color}30`,
                      background: `${currentLevelMeta.color}0c`,
                    }}
                  >
                    <span
                      style={{
                        ...{
                          display: "flex",
                          flexShrink: 0,
                        },
                        color: currentLevelMeta.color,
                      }}
                    >
                      {Ic.lock(13)}
                    </span>
                    <span
                      style={{
                        ...{
                          fontSize: 11,
                          fontWeight: 700,
                          fontFamily: F.sans,
                          letterSpacing: 0.4,
                        },
                        color: currentLevelMeta.color,
                      }}
                    >
                      REE SEALED
                    </span>
                    <span
                      style={{
                        ...{
                          marginLeft: "auto",
                          fontSize: 9,
                          fontFamily: F.mono,
                          borderRadius: 3,
                          padding: "1px 6px",
                          letterSpacing: 0.6,
                          fontWeight: 700,
                        },
                        color: currentLevelMeta.color,
                        background: `${currentLevelMeta.color}18`,
                        border: `1px solid ${currentLevelMeta.color}40`,
                      }}
                    >
                      L{level} · {currentLevelMeta.label}
                    </span>
                  </div>
                  <div
                    style={{
                      padding: "10px 14px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                    }}
                  >
                    <div style={S_OVERVIEW_SEALED_META_ROW}>
                      <span style={S_OVERVIEW_SEALED_META_KEY}>hash</span>
                      <span
                        style={{
                          fontFamily: F.mono,
                          fontSize: 11,
                          color: C.text,
                          fontWeight: 600,
                          letterSpacing: 0.8,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {ree._sealHash || "—"}
                      </span>
                    </div>
                    <div style={S_OVERVIEW_SEALED_META_ROW}>
                      <span style={S_OVERVIEW_SEALED_META_KEY}>sealed</span>
                      <span
                        style={{
                          fontFamily: F.mono,
                          fontSize: 10,
                          color: C.textMid,
                        }}
                      >
                        {sealDate}
                      </span>
                    </div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 3,
                        marginTop: 2,
                      }}
                    >
                      {cableItems.map((c) => (
                        <div
                          key={c.label}
                          title={c.label}
                          style={{
                            flex: 1,
                            height: 3,
                            borderRadius: 99,
                            background: c.live ? currentLevelMeta.color : "#d1d5db",
                            opacity: c.live ? 0.85 : 0.4,
                          }}
                        />
                      ))}
                    </div>
                    {onPreviewReviewer && (
                      <button
                        type="button"
                        onClick={onPreviewReviewer}
                        style={{
                          ...S_OVERVIEW_SEALED_ACTION_BTN_BASE,
                          background: `linear-gradient(135deg, ${currentLevelMeta.color}18 0%, ${currentLevelMeta.color}0c 100%)`,
                          border: `1.5px solid ${currentLevelMeta.color}50`,
                          color: currentLevelMeta.color,
                        }}
                        {...hoverBg(
                          `${currentLevelMeta.color}28`,
                          `linear-gradient(135deg, ${currentLevelMeta.color}18 0%, ${currentLevelMeta.color}0c 100%)`,
                        )}
                        {...hoverBorderColor(
                          `${currentLevelMeta.color}80`,
                          `${currentLevelMeta.color}50`,
                        )}
                      >
                        {Ic.star(12)}
                        Preview as Reviewer
                      </button>
                    )}
                    {onDownloadRee && (
                      <button
                        type="button"
                        onClick={onDownloadRee}
                        style={{
                          ...S_OVERVIEW_SEALED_ACTION_BTN_BASE,
                          background: "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)",
                          border: "1.5px solid #86efac",
                          color: "#15803d",
                        }}
                        {...hoverBg("#bbf7d0", "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)")}
                        {...hoverBorderColor("#4ade80", "#86efac")}
                      >
                        {Ic.download(12)}
                        Download REE
                      </button>
                    )}
                  </div>
                </div>
              );
            }

            return (
              <>
                {/* Confirmation modal */}
                {showSealConfirm && (
                  <div
                    style={{
                      position: "fixed",
                      inset: 0,
                      zIndex: 9999,
                      background: "rgba(0,0,0,0.45)",
                      backdropFilter: "blur(3px)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <button
                      type="button"
                      aria-label="Close confirmation"
                      onClick={() => setShowSealConfirm(false)}
                      style={{
                        position: "absolute",
                        inset: 0,
                        border: "none",
                        background: "transparent",
                        padding: 0,
                        margin: 0,
                        cursor: "default",
                      }}
                    />
                    <div
                      style={{
                        background: C.surface,
                        borderRadius: 14,
                        width: 380,
                        maxWidth: "90vw",
                        border: `1.5px solid ${C.border}`,
                        boxShadow: "0 8px 40px rgba(0,0,0,0.22)",
                        overflow: "hidden",
                        position: "relative",
                        zIndex: 1,
                      }}
                    >
                      {/* Modal header */}
                      <div
                        style={{
                          padding: "16px 20px 12px",
                          borderBottom: `1px solid ${C.border}`,
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                          }}
                        >
                          <div
                            style={{
                              ...{
                                width: 32,
                                height: 32,
                                borderRadius: 8,
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                flexShrink: 0,
                              },
                              background: `${currentLevelMeta.color}18`,
                            }}
                          >
                            <span
                              style={{
                                ...{
                                  display: "flex",
                                },
                                color: currentLevelMeta.color,
                              }}
                            >
                              {Ic.lock(16)}
                            </span>
                          </div>
                          <div>
                            <div
                              style={{
                                fontSize: 14,
                                fontWeight: 700,
                                fontFamily: F.sans,
                                color: C.text,
                              }}
                            >
                              Seal this REE?
                            </div>
                            <div
                              style={{
                                fontSize: 11,
                                fontFamily: F.sans,
                                color: C.textMuted,
                                marginTop: 1,
                              }}
                            >
                              This action cannot be undone.
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Warning: missing cables */}
                      {!allLive && (
                        <div
                          style={{
                            margin: "12px 20px 0",
                            padding: "10px 12px",
                            borderRadius: 8,
                            background: "#fffbeb",
                            border: "1.5px solid #fde68a",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              alignItems: "flex-start",
                              gap: 8,
                            }}
                          >
                            <span
                              style={{
                                fontSize: 15,
                                flexShrink: 0,
                                lineHeight: 1.2,
                              }}
                            >
                              ⚠️
                            </span>
                            <div>
                              <div
                                style={{
                                  fontSize: 11,
                                  fontWeight: 700,
                                  fontFamily: F.sans,
                                  color: "#92400e",
                                  marginBottom: 5,
                                }}
                              >
                                {missing.length} panel{missing.length !== 1 ? "s" : ""} not
                                connected
                              </div>
                              <div
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  gap: 3,
                                }}
                              >
                                {missing.map((m) => (
                                  <div
                                    key={m.key}
                                    style={{
                                      display: "flex",
                                      alignItems: "center",
                                      gap: 6,
                                    }}
                                  >
                                    <div
                                      style={{
                                        width: 5,
                                        height: 5,
                                        borderRadius: "50%",
                                        background: "#f59e0b",
                                        flexShrink: 0,
                                      }}
                                    />
                                    <span
                                      style={{
                                        fontSize: 10,
                                        fontFamily: F.sans,
                                        color: "#92400e",
                                      }}
                                    >
                                      {m.label} — not completed
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Body copy */}
                      <div
                        style={{
                          padding: "12px 20px",
                        }}
                      >
                        <div
                          style={{
                            fontSize: 12,
                            fontFamily: F.sans,
                            color: C.textMid,
                            lineHeight: 1.6,
                          }}
                        >
                          {allLive ? (
                            <>
                              All <strong>{totalCables}</strong> panels are connected. The REE will
                              be frozen at{" "}
                              <strong>
                                L{level} · {currentLevelMeta.label}
                              </strong>{" "}
                              and become read-only.
                            </>
                          ) : (
                            <>
                              Sealing now will freeze the REE at{" "}
                              <strong>
                                L{level} · {currentLevelMeta.label}
                              </strong>{" "}
                              with incomplete data. You can still seal, but the missing panels will
                              not be part of the record.
                            </>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div
                        style={{
                          padding: "0 20px 16px",
                          display: "flex",
                          gap: 8,
                          justifyContent: "flex-end",
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => setShowSealConfirm(false)}
                          style={{
                            ...S_ACTION_BUTTON_BASE,
                            padding: "8px 16px",
                            borderRadius: 7,
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: "pointer",
                            background: C.surfaceAlt,
                            color: C.textMid,
                            border: `1.5px solid ${C.border}`,
                          }}
                          {...hoverBg(C.border, C.surfaceAlt)}
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setShowSealConfirm(false);
                            onSeal?.();
                          }}
                          style={{
                            ...{
                              ...S_ACTION_BUTTON_BASE,
                              display: "flex",
                              alignItems: "center",
                              gap: 7,
                              padding: "8px 18px",
                              borderRadius: 7,
                              fontSize: 12,
                              fontWeight: 700,
                              cursor: "pointer",
                              color: "#fff",
                            },
                            background: currentLevelMeta.color,
                            border: `1.5px solid ${currentLevelMeta.color}`,
                            boxShadow: `0 2px 8px ${currentLevelMeta.color}50`,
                          }}
                          {...hoverBrightness(90)}
                        >
                          <span style={{ display: "flex" }}>{Ic.lock(12)}</span>
                          {allLive ? "Seal REE" : "Seal anyway"}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Seal strip */}
                <div
                  ref={sealRef}
                  style={{
                    width: "100%",
                    maxWidth: 480,
                    background: C.surface,
                    border: `1.5px solid ${C.border}`,
                    borderRadius: 10,
                    overflow: "hidden",
                  }}
                >
                  {/* Progress row */}
                  <div
                    style={{
                      padding: "9px 14px",
                      borderBottom: `1px solid ${C.border}`,
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 10,
                        fontFamily: F.sans,
                        color: C.textMuted,
                        flexShrink: 0,
                      }}
                    >
                      {liveCount}/{totalCables} connected
                    </span>
                    <div
                      style={{
                        flex: 1,
                        display: "flex",
                        gap: 3,
                        alignItems: "center",
                      }}
                    >
                      {cableItems.map((c) => (
                        <div
                          key={c.label}
                          title={c.label}
                          style={{
                            flex: 1,
                            height: 3,
                            borderRadius: 99,
                            background: c.live ? currentLevelMeta.color : C.border,
                            transition: "background 0.3s",
                          }}
                        />
                      ))}
                    </div>
                    {allLive ? (
                      <span
                        style={{
                          ...S_OVERVIEW_SEAL_STATUS_BADGE_BASE,
                          color: currentLevelMeta.color,
                          background: `${currentLevelMeta.color}14`,
                          border: `1px solid ${currentLevelMeta.color}40`,
                        }}
                      >
                        ready
                      </span>
                    ) : (
                      <span
                        style={{
                          ...S_OVERVIEW_SEAL_STATUS_BADGE_BASE,
                          color: "#d97706",
                          background: "#fffbeb",
                          border: "1px solid #fde68a",
                        }}
                      >
                        incomplete
                      </span>
                    )}
                  </div>
                  {/* Seal button row */}
                  <div
                    style={{
                      padding: "10px 14px",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                    }}
                  >
                    <div
                      style={{
                        flex: 1,
                      }}
                    >
                      <div
                        style={{
                          fontSize: 11,
                          fontFamily: F.sans,
                          fontWeight: 600,
                          color: C.text,
                        }}
                      >
                        Seal REE
                      </div>
                      <div
                        style={{
                          ...{
                            fontSize: 10,
                            fontFamily: F.sans,
                            marginTop: 2,
                          },
                          color: allLive ? C.textMuted : "#d97706",
                        }}
                      >
                        {allLive
                          ? `L${level} · ${currentLevelMeta.label} — all panels connected`
                          : `${missing.length} panel${missing.length !== 1 ? "s" : ""} not yet connected`}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowSealConfirm(true)}
                      style={{
                        ...{
                          ...S_ACTION_BUTTON_BASE,
                          display: "flex",
                          alignItems: "center",
                          gap: 7,
                          padding: "8px 18px",
                          borderRadius: 7,
                          flexShrink: 0,
                          fontSize: 12,
                          fontWeight: 700,
                          letterSpacing: 0.3,
                          cursor: "pointer",
                          color: "#fff",
                          transition: "all 0.2s",
                        },
                        background: currentLevelMeta.color,
                        border: `1.5px solid ${currentLevelMeta.color}`,
                        boxShadow: `0 2px 10px ${currentLevelMeta.color}50`,
                      }}
                      {...hoverBrightness(92)}
                    >
                      <span
                        style={{
                          display: "flex",
                        }}
                      >
                        {Ic.lock(13)}
                      </span>
                      Seal
                    </button>
                  </div>
                </div>
              </>
            );
          })()}
        </div>

        {/* Right — swh + evaluate + archive + verification */}
        <div
          style={{
            width: 196,
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
            gap: 14,
            position: "relative",
            zIndex: 1,
          }}
        >
          {/* Software Heritage panel */}
          <div ref={swhRef} style={panel({ overflow: "hidden" })}>
            <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
              <div
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: "50%",
                  background: "#e4572e",
                  boxShadow: ree.swhid ? "0 0 5px #e4572e99" : "none",
                }}
              />
              <span style={S_PANEL_HEADER_LABEL}>Software Heritage</span>
              <span
                style={{
                  ...S_OVERVIEW_PANEL_BADGE_BASE,
                  color: "#e4572e",
                  background: "#fff7f5",
                  border: "1px solid #fbd0c4",
                }}
              >
                SWH
              </span>
            </div>
            <PanelFieldRow
              label="SWHID"
              value={ree.swhid || null}
              filled={!!ree.swhid}
              dotColor="#e4572e"
              dotGlow="#e4572e99"
              labelColor="#9a3412"
              labelBg="#fff7f5"
              labelBorderColor="#e4572e25"
              emptyText="not archived"
              isLast
              onClick={() => onNavigate?.(PAGE.SWH)}
            />
            <div style={S_OVERVIEW_PANEL_FOOTER}>
              <button
                type="button"
                onClick={() => onNavigate?.(PAGE.SWH)}
                style={{
                  ...S_OVERVIEW_PANEL_BUTTON_BASE,
                  color: "#9a3412",
                  background: "#fff7f5",
                  border: "1px solid #fbd0c4",
                }}
                {...hoverBrightness(95)}
              >
                → Go to Software Heritage
              </button>
            </div>
          </div>

          {/* Evaluate panel */}
          {(() => {
            const svc = SERVICES.find((service) => service.key === PAGE.EVALUATE);
            if (!svc) return null;
            const earned = !!badges[svc.key];
            const ts = timestamps[svc.key];
            const dateStr = ts
              ? new Date(ts).toLocaleString([], {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : null;
            return (
              <div ref={evaluateRef} style={panel({ overflow: "hidden" })}>
                <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
                  <div
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: "50%",
                      background: earned ? svc.badge.color : "#d1d5db",
                      boxShadow: earned ? `0 0 5px ${svc.badge.color}99` : "none",
                    }}
                  />
                  <span style={S_PANEL_HEADER_LABEL}>Evaluate</span>
                  {earned && (
                    <span
                      style={{
                        ...S_OVERVIEW_PANEL_BADGE_BASE,
                        color: svc.badge.color,
                        background: svc.badge.bg,
                        border: `1px solid ${svc.badge.color}40`,
                      }}
                    >
                      OK
                    </span>
                  )}
                </div>
                <div style={S_OVERVIEW_META_FOOTER}>
                  <div style={S_FLEX_ROW_CENTER_GAP_6}>
                    <span
                      style={{ display: "flex", color: earned ? svc.badge.color : C.textMuted }}
                    >
                      {Ic.star(12)}
                    </span>
                    <span
                      style={{
                        fontSize: 10,
                        fontFamily: F.sans,
                        color: earned ? C.text : C.textMuted,
                        flex: 1,
                      }}
                    >
                      {earned ? `L${level} — ${LEVELS[Math.min(level, 7)].label}` : "Not evaluated"}
                    </span>
                  </div>
                  {earned && dateStr && (
                    <div
                      style={{
                        fontSize: 9,
                        fontFamily: F.mono,
                        color: C.textMuted,
                        letterSpacing: 0.2,
                      }}
                    >
                      {dateStr}
                    </div>
                  )}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 5,
                      padding: "5px 8px",
                      borderRadius: 5,
                      background: earned ? svc.badge.bg : C.surfaceAlt,
                      border: `1px solid ${earned ? `${svc.badge.color}40` : C.border}`,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 10,
                        fontFamily: F.sans,
                        color: earned ? svc.badge.color : C.textMuted,
                        fontWeight: 600,
                      }}
                    >
                      {earned ? "✓ score computed" : "run Evaluate"}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => onNavigate?.(svc.key)}
                    style={{
                      ...S_OVERVIEW_PANEL_BUTTON_BASE,
                      color: svc.badge.color,
                      background: svc.badge.bg,
                      border: `1px solid ${svc.badge.color}40`,
                    }}
                    {...hoverBrightness(95)}
                  >
                    → Go to Evaluate
                  </button>
                </div>
              </div>
            );
          })()}

          {/* Archival & DOIs — Zenodo + Dataverse only */}
          <OverviewPanel
            ref={archiveRef}
            color="#059669"
            label="Archival & DOIs"
            fields={[
              {
                label: "Zenodo",
                value: ree.zenodo_doi ? (ree.zenodo_doi as string) : null,
                filled: !!ree.zenodo_doi && (ree.zenodo_doi as string).trim().length > 0,
                emptyText: "unregistered",
                onClick: () => onNavigate?.(PAGE.ARCHIVE),
              },
              {
                label: "Dataverse",
                value: ree.dataverse_doi ? (ree.dataverse_doi as string) : null,
                filled: !!ree.dataverse_doi && (ree.dataverse_doi as string).trim().length > 0,
                emptyText: "unregistered",
                onClick: () => onNavigate?.(PAGE.ARCHIVE),
              },
            ]}
            footerLabel="Go to Archival & DOIs"
            onFooterClick={() => onNavigate?.(PAGE.ARCHIVE)}
          />

          {/* Test Activation panel */}
          {(() => {
            const activationColor = "#7c3aed";
            const activationEarned = !!badges?.activation;
            const as = ree.activation_script;
            const asFilled = !!as;
            const asLabel = FIELD_META.activation_script?.label || "Activation script";
            return (
              <div ref={activationRef} style={panel({ overflow: "hidden" })}>
                <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
                  <div
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: "50%",
                      background: activationColor,
                      boxShadow: activationEarned ? `0 0 5px ${activationColor}99` : "none",
                    }}
                  />
                  <span style={S_PANEL_HEADER_LABEL}>Test Activation</span>
                  {activationEarned && (
                    <span
                      style={{
                        ...S_OVERVIEW_PANEL_BADGE_BASE,
                        color: activationColor,
                        background: "#f5f3ff",
                        border: `1px solid ${activationColor}40`,
                      }}
                    >
                      OK
                    </span>
                  )}
                </div>
                {/* activation_script field row */}
                <PanelFieldRow
                  label={asLabel}
                  value={asFilled ? as : null}
                  filled={asFilled}
                  dotColor="#7c3aed"
                  dotGlow="#7c3aed99"
                  labelColor="#5b21b6"
                  labelBg="#f5f3ff"
                  labelBorderColor="#7c3aed25"
                  isLast
                  onClick={() => onGoField?.("activation_script")}
                />
                {/* Go to Test Activation button */}
                <div style={S_OVERVIEW_PANEL_FOOTER}>
                  <button
                    type="button"
                    onClick={() => onNavigate?.(PAGE.ACTIVATION)}
                    style={{
                      ...S_OVERVIEW_PANEL_BUTTON_BASE,
                      color: activationColor,
                      background: "#f5f3ff",
                      border: `1px solid ${activationColor}40`,
                    }}
                    {...hoverBrightness(95)}
                  >
                    → Go to Test Activation
                  </button>
                </div>
              </div>
            );
          })()}
        </div>
      </div>

      {/* ── Horizontal level strip ── */}
      <div style={{ marginTop: 20, display: "flex", alignItems: "center" }}>
        {LEVELS.map((levelConfig, i) => {
          const isReached = i <= level;
          const isCurrent = i === level;
          const isLast = i === LEVELS.length - 1;
          return (
            <React.Fragment key={levelConfig.n}>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 5,
                  flex: 1,
                }}
              >
                <div
                  style={{
                    width: isCurrent ? 14 : 9,
                    height: isCurrent ? 14 : 9,
                    borderRadius: "50%",
                    background: isReached ? levelConfig.color : C.border,
                    border: isCurrent ? `2.5px solid ${levelConfig.color}` : "none",
                    boxShadow: isCurrent ? `0 0 0 4px ${levelConfig.color}22` : "none",
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    fontFamily: F.mono,
                    letterSpacing: 0.4,
                    color: isReached ? levelConfig.ink : C.textMuted,
                    background: isReached ? `${levelConfig.color}18` : C.surfaceAlt,
                    border: `1px solid ${isReached ? `${levelConfig.color}40` : C.border}`,
                    borderRadius: 3,
                    padding: "0 5px",
                    lineHeight: "18px",
                    whiteSpace: "nowrap",
                  }}
                >
                  L{i}
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: isCurrent ? 700 : 400,
                    color: isCurrent ? C.text : isReached ? C.textMid : C.textMuted,
                    fontFamily: F.sans,
                    whiteSpace: "nowrap",
                  }}
                >
                  {levelConfig.label}
                </span>
              </div>
              {!isLast && (
                <div
                  style={{
                    height: 2,
                    flex: 1,
                    maxWidth: 28,
                    background: i < level ? levelConfig.color : C.border,
                    borderRadius: 1,
                    flexShrink: 0,
                    marginBottom: 34,
                  }}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* ── All REE Fields (Readonly) ── */}
      <div
        style={{
          marginTop: 32,
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: "16px 20px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <div style={{ width: 5, height: 5, borderRadius: "50%", background: C.textMuted }} />
          <span
            style={{
              fontSize: 12,
              fontWeight: 700,
              color: C.text,
              letterSpacing: 0.3,
              fontFamily: F.sans,
            }}
          >
            All Fields
          </span>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          {Object.entries(ree)
            .filter(([k]) => !k.startsWith("_"))
            .map(([k, v], idx, arr) => {
              const label = FIELD_META[k]?.label || k;
              const isEmpty =
                v === undefined ||
                v === null ||
                v === "" ||
                (typeof v === "object" && Object.keys(v).length === 0);
              let displayVal = isEmpty ? "not set" : v;
              if (typeof v === "object" && v !== null && !isEmpty) {
                displayVal = JSON.stringify(v, null, 2);
              }
              const isLastRow = idx === arr.length - 1;
              return (
                <div
                  key={k}
                  style={{
                    display: "flex",
                    padding: "10px 0",
                    borderBottom: isLastRow ? "none" : `1px solid ${C.border}`,
                    alignItems: "flex-start",
                    gap: 16,
                  }}
                >
                  <div
                    style={{ width: 180, display: "flex", flexDirection: "column", flexShrink: 0 }}
                  >
                    <span
                      style={{
                        fontSize: 11,
                        fontFamily: F.sans,
                        color: C.textMid,
                        fontWeight: 600,
                      }}
                    >
                      {label}
                    </span>
                    <span style={{ fontFamily: F.mono, fontSize: 9, color: C.textMuted }}>{k}</span>
                  </div>
                  {typeof v === "object" && v !== null && !isEmpty ? (
                    <pre
                      style={{
                        margin: 0,
                        fontSize: 11,
                        fontFamily: F.mono,
                        color: C.textMid,
                        whiteSpace: "pre-wrap",
                        background: C.surfaceAlt,
                        padding: "8px 12px",
                        borderRadius: 6,
                        flex: 1,
                        border: `1px solid ${C.border}`,
                      }}
                    >
                      {String(displayVal)}
                    </pre>
                  ) : (
                    <span
                      style={{
                        fontSize: 12,
                        fontFamily: F.mono,
                        color: isEmpty ? C.textMuted : C.text,
                        fontStyle: isEmpty ? "italic" : "normal",
                        wordBreak: "break-all",
                        flex: 1,
                        marginTop: 1,
                      }}
                    >
                      {String(displayVal)}
                    </span>
                  )}
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}
