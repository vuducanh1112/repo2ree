import type React from "react";
import { Ic } from "../../../../components/Icon";
import { type ExplorerPage, PAGE } from "../../../../constants/pages";
import { C, F, hoverBg, S_ACTION_BUTTON_BASE } from "../../../../constants/theme";
import type { Badges, RequirementsBannerProps, ServiceBadge } from "../../../../types";

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

interface NextStepNudgeProps {
  stepKey: string;
  badges: Badges;
  onGo: (key: ExplorerPage) => void;
}
export function NextStepNudge({ stepKey, onGo }: NextStepNudgeProps) {
  const Steps: Array<{
    key: ExplorerPage;
    nextKey: ExplorerPage | null;
    nextLabel: string | null;
    cond: () => boolean;
  }> = [
    { key: PAGE.SOURCE, nextKey: PAGE.METADATA, nextLabel: "Provide Metadata", cond: () => true },
    {
      key: PAGE.METADATA,
      nextKey: PAGE.HBOM,
      nextLabel: "Create Hardware BOM",
      cond: () => true,
    },
    { key: PAGE.HBOM, nextKey: PAGE.EVALUATE, nextLabel: "Evaluate", cond: () => true },
    { key: PAGE.EVALUATE, nextKey: PAGE.BUILD, nextLabel: "Build Runtime", cond: () => true },
    { key: PAGE.BUILD, nextKey: PAGE.SBOM, nextLabel: "Generate SBOM", cond: () => true },
    { key: PAGE.SBOM, nextKey: PAGE.ACTIVATION, nextLabel: "Test Activation", cond: () => true },
    {
      key: PAGE.ACTIVATION,
      nextKey: PAGE.ARCHIVE,
      nextLabel: "Deposit & Share",
      cond: () => true,
    },
    { key: PAGE.ARCHIVE, nextKey: PAGE.SEAL, nextLabel: "Seal", cond: () => true },
    { key: PAGE.SEAL, nextKey: null, nextLabel: null, cond: () => false },
  ];
  const step = Steps.find((workflowStep) => workflowStep.key === stepKey);
  const nextKey = step?.nextKey;
  const nextLabel = step?.nextLabel;
  if (!step || !nextKey || !nextLabel) return null;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "9px 14px",
        background: C.accentBg,
        border: `1px solid ${C.accentBorder}`,
        borderRadius: 9,
        marginBottom: 20,
        animation: "fadeUp 0.2s ease",
      }}
    >
      <span style={{ color: C.accent, display: "flex", flexShrink: 0 }}>{Ic.chevR()}</span>
      <span style={{ fontSize: 13, color: C.textMid, fontFamily: F.sans, flex: 1 }}>
        Next step:
      </span>
      <button
        type="button"
        onClick={() => onGo(nextKey)}
        style={{
          ...actionBtn({
            border: "none",
            padding: "5px 12px",
            background: C.accent,
            color: "#fff",
          }),
          display: "flex",
          alignItems: "center",
          gap: 5,
          cursor: "pointer",
          flexShrink: 0,
          borderRadius: 6,
          transition: "background 0.13s",
        }}
        {...hoverBg("#1d4ed8", C.accent)}
      >
        {nextLabel} →
      </button>
    </div>
  );
}

interface WorkflowPageHeaderProps {
  color: string;
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  tips?: string[];
  runDone?: boolean;
  badge?: ServiceBadge | null;
  ts?: string;
  timestampPrefix?: string;
  missingCount?: number;
  onGoFields?: () => void;
  rightAction?: React.ReactNode;
}
export function WorkflowPageHeader({
  color,
  icon,
  title,
  subtitle,
  tips = [],
  runDone,
  badge,
  ts,
  timestampPrefix = "Last run",
  missingCount = 0,
  onGoFields,
  rightAction,
}: WorkflowPageHeaderProps) {
  return (
    <div
      style={{
        flexShrink: 0,
        padding: "16px 28px 14px",
        borderBottom: `1px solid ${C.border}`,
        background: "rgba(255,255,255,0.7)",
        backdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "center",
        gap: 14,
      }}
    >
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 10,
          background: `${color}18`,
          color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: C.text, letterSpacing: -0.2 }}>
            {title}
          </span>
          {runDone && badge && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: badge.color,
                background: badge.bg,
                border: `1px solid ${badge.color}40`,
                borderRadius: 99,
                padding: "2px 9px",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              {Ic.check(10)} {badge.label}
            </span>
          )}
          {missingCount > 0 && onGoFields && (
            <button
              type="button"
              style={{
                ...actionBtn({
                  fontSize: 11,
                  borderRadius: 99,
                  padding: "2px 9px",
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  color: "#dc2626",
                  transition: "all 0.12s",
                }),
                display: "flex",
                alignItems: "center",
                gap: 4,
                cursor: "pointer",
              }}
              onClick={onGoFields}
            >
              {Ic.info(10)} {missingCount} missing field{missingCount > 1 ? "s" : ""} ← fix
            </button>
          )}
        </div>
        <div style={{ fontSize: 12, color: C.textMuted, marginTop: 1 }}>{subtitle}</div>
        {tips.length > 0 && (
          <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 3 }}>
            {tips.map((tip) => (
              <div
                key={tip}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 6,
                  fontSize: 11,
                  color: C.textMid,
                  lineHeight: 1.4,
                  fontFamily: F.sans,
                }}
              >
                <span style={{ color, display: "flex", marginTop: 1, flexShrink: 0 }}>
                  {Ic.info(10)}
                </span>
                <span>{tip}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      {rightAction}
      {runDone && ts && (
        <span style={{ fontSize: 11, color: C.textMuted, fontFamily: F.mono, flexShrink: 0 }}>
          {timestampPrefix}{" "}
          {new Date(ts).toLocaleString([], {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      )}
    </div>
  );
}

export function RequirementsBanner({
  status,
  items = [],
  onAction,
  actionLabel,
}: RequirementsBannerProps) {
  const isMissing = status === "missing";

  return (
    <div
      style={{
        background: isMissing ? "#fef2f2" : "#f0fdf4",
        border: `1px solid ${isMissing ? "#fecaca" : "#bbf7d0"}`,
        borderRadius: 10,
        padding: "12px 16px",
        marginBottom: 20,
        display: "flex",
        gap: 12,
        alignItems: "flex-start",
      }}
    >
      <span
        style={{
          color: isMissing ? "#dc2626" : "#16a34a",
          flexShrink: 0,
          marginTop: 1,
          display: "flex",
        }}
      >
        {isMissing ? Ic.info() : Ic.check()}
      </span>
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: isMissing ? "#dc2626" : "#16a34a",
            marginBottom: items.length > 0 ? 5 : 0,
          }}
        >
          {isMissing ? "Missing required fields" : "All required fields set"}
        </div>

        {items.length > 0 && (
          <div
            style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: onAction ? 8 : 0 }}
          >
            {items.map((item) => (
              <span
                key={item.field}
                style={{
                  fontSize: 12,
                  fontFamily: F.sans,
                  color: isMissing ? "#dc2626" : "#16a34a",
                  background: isMissing ? "#fff" : "#dcfce7",
                  border: `1px solid ${isMissing ? "#fecaca" : "#bbf7d0"}`,
                  borderRadius: 4,
                  padding: "2px 8px",
                }}
              >
                {item.label}
              </span>
            ))}
          </div>
        )}

        {onAction && actionLabel && (
          <button
            type="button"
            onClick={onAction}
            style={{
              ...actionBtn({
                border: `1px solid ${C.accentBorder}`,
                borderRadius: 6,
                padding: "4px 10px",
                background: "transparent",
                color: C.accent,
              }),
              cursor: "pointer",
            }}
          >
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  );
}
