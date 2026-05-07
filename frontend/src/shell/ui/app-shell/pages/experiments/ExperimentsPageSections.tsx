import type React from "react";
import { useEffect, useRef, useState } from "react";
import type { ReeExperiment } from "../../../../../core/ree/ReeSpec";
import { Ic, Svg } from "../../../shared/components/Icon";
import {
  C,
  F,
  S_ACTION_BUTTON_BASE,
  S_FLEX_ROW_CENTER_GAP_6,
  S_SECTION_LABEL_SMALL,
} from "../../../theme/theme";
import { expId, ICON_ARROW_LEFT, ICON_CHEV_RIGHT } from "./experimentsPageHelpers";

const COL_TEMPLATE = "72px 1fr 1fr 28px";

// ── Inline editable field ────────────────────────────────────────────────────

function EditableText({
  value,
  readOnly,
  onChange,
  placeholder,
  style,
  inputStyle,
}: {
  value: string;
  readOnly?: boolean;
  onChange: (v: string) => void;
  placeholder: string;
  style?: React.CSSProperties;
  inputStyle?: React.CSSProperties;
}) {
  const [editing, setEditing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const commit = () => setEditing(false);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  if (editing && !readOnly) {
    return (
      <input
        ref={inputRef}
        value={value}
        autoCorrect="off"
        autoCapitalize="none"
        spellCheck={false}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => (e.key === "Enter" || e.key === "Escape") && commit()}
        style={{
          background: "transparent",
          border: "none",
          borderBottom: `1.5px solid ${C.accent}`,
          outline: "none",
          padding: "0 0 2px",
          margin: 0,
          width: "100%",
          fontFamily: F.sans,
          ...style,
          ...inputStyle,
        }}
      />
    );
  }

  return (
    <button
      type="button"
      onClick={() => !readOnly && setEditing(true)}
      title={readOnly ? undefined : "Click to edit"}
      style={{
        background: "none",
        border: "none",
        padding: 0,
        margin: 0,
        cursor: readOnly ? "default" : "text",
        textAlign: "left",
        width: "100%",
        fontFamily: F.sans,
        ...style,
      }}
    >
      {value || <span style={{ opacity: 0.35 }}>{placeholder}</span>}
    </button>
  );
}

// ── Catalog table ────────────────────────────────────────────────────────────

export function CatalogTable({
  experiments,
  locked,
  onSelect,
  onAdd,
}: {
  experiments: ReeExperiment[];
  locked: boolean;
  onSelect: (index: number) => void;
  onAdd: () => void;
}) {
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: COL_TEMPLATE,
          padding: "7px 16px",
          background: C.surfaceAlt,
          borderBottom: `1px solid ${C.border}`,
          alignItems: "center",
        }}
      >
        {["ID", "Name", "Command", ""].map((label) => (
          <span key={label} style={S_SECTION_LABEL_SMALL}>
            {label}
          </span>
        ))}
      </div>

      {experiments.length === 0 ? (
        <EmptyState />
      ) : (
        experiments.map((exp, index) => (
          <CatalogRow
            key={`exp-${String(index)}`}
            experiment={exp}
            index={index}
            isLast={index === experiments.length - 1}
            onSelect={() => onSelect(index)}
          />
        ))
      )}

      <AddRow onClick={onAdd} hasExperiments={experiments.length > 0} disabled={locked} />
    </div>
  );
}

function CatalogRow({
  experiment,
  index,
  isLast,
  onSelect,
}: {
  experiment: ReeExperiment;
  index: number;
  isLast: boolean;
  onSelect: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <button
      type="button"
      onClick={onSelect}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "grid",
        gridTemplateColumns: COL_TEMPLATE,
        padding: "11px 16px",
        background: hovered ? C.accentBg : C.surface,
        borderBottom: isLast ? "none" : `1px solid ${C.border}`,
        borderLeft: "none",
        borderRight: "none",
        borderTop: "none",
        width: "100%",
        cursor: "pointer",
        transition: "background 0.1s",
        alignItems: "center",
        textAlign: "left",
      }}
    >
      <span
        style={{
          fontFamily: F.mono,
          fontSize: 10,
          color: hovered ? C.accent : C.textMuted,
          fontWeight: 700,
          letterSpacing: "0.07em",
          transition: "color 0.1s",
        }}
      >
        {expId(index)}
      </span>

      <span
        style={{
          fontSize: 13,
          fontFamily: F.sans,
          fontWeight: 500,
          color: experiment.name.trim() ? C.text : C.textMuted,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          paddingRight: 12,
        }}
      >
        {experiment.name.trim() || <em style={{ fontStyle: "normal", opacity: 0.5 }}>untitled</em>}
      </span>

      <span
        style={{
          fontSize: 12,
          fontFamily: F.mono,
          color: experiment.command.trim() ? C.textMid : C.textMuted,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          paddingRight: 12,
          opacity: experiment.command.trim() ? 1 : 0.6,
        }}
      >
        {experiment.command.trim() || "—"}
      </span>

      <span
        style={{
          color: hovered ? C.accent : C.borderMid,
          display: "flex",
          justifyContent: "flex-end",
          transition: "color 0.1s",
        }}
      >
        <Svg d={ICON_CHEV_RIGHT} size={13} sw={2} />
      </span>
    </button>
  );
}

function EmptyState() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        padding: "48px 24px",
        color: C.textMuted,
        fontFamily: F.sans,
        fontSize: 13,
        textAlign: "center",
        lineHeight: 1.6,
      }}
    >
      <span style={{ color: C.borderMid, marginBottom: 4 }}>{Ic.terminal(28)}</span>
      No experiments registered yet.
      <span style={{ fontSize: 12, maxWidth: 300 }}>
        Add one below to define reproducibility verification commands.
      </span>
    </div>
  );
}

function AddRow({
  onClick,
  hasExperiments,
  disabled,
}: {
  onClick: () => void;
  hasExperiments: boolean;
  disabled: boolean;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 7,
        padding: "10px 16px",
        background: hovered && !disabled ? C.accentBg : "transparent",
        border: "none",
        borderTop: hasExperiments ? `1px dashed ${C.border}` : "none",
        cursor: disabled ? "default" : "pointer",
        color: hovered && !disabled ? C.accent : C.textMuted,
        opacity: disabled ? 0.4 : 1,
        fontSize: 12,
        fontFamily: F.sans,
        fontWeight: 500,
        transition: "background 0.1s, color 0.1s",
        borderRadius: "0 0 10px 10px",
      }}
    >
      <span style={{ display: "flex" }}>{Ic.plus(14)}</span>
      Add experiment
    </button>
  );
}

// ── Detail view ──────────────────────────────────────────────────────────────

export function ExperimentDetail({
  experiment,
  index,
  locked,
  onUpdate,
  onBack,
  onRemove,
}: {
  experiment: ReeExperiment;
  index: number;
  locked: boolean;
  onUpdate: (patch: Partial<ReeExperiment>) => void;
  onBack: () => void;
  onRemove: () => void;
}) {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflowY: "auto" }}>
      <div
        style={{
          ...S_FLEX_ROW_CENTER_GAP_6,
          padding: "8px 20px",
          borderBottom: `1px solid ${C.border}`,
          background: C.surface,
          flexShrink: 0,
        }}
      >
        <button
          type="button"
          onClick={onBack}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            background: "none",
            border: "none",
            cursor: "pointer",
            color: C.textMid,
            fontSize: 12,
            fontFamily: F.sans,
            padding: "4px 6px",
            borderRadius: 5,
          }}
        >
          <Svg d={ICON_ARROW_LEFT} size={13} sw={1.8} />
          ReeExperiments
        </button>
        <span style={{ color: C.border }}>/</span>
        <span
          style={{
            fontFamily: F.mono,
            fontSize: 11,
            color: C.accent,
            fontWeight: 700,
            letterSpacing: "0.07em",
          }}
        >
          {expId(index)}
        </span>
        <span style={{ flex: 1 }} />
        <button
          type="button"
          disabled
          style={{
            ...S_ACTION_BUTTON_BASE,
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 12px",
            borderRadius: 6,
            background: C.accent,
            border: "none",
            color: "#fff",
            fontSize: 12,
            fontFamily: F.sans,
            fontWeight: 600,
            opacity: 0.5,
            cursor: "default",
          }}
        >
          {Ic.play(12)}
          Run
        </button>
        {!locked && <DeleteButton onClick={onRemove} />}
      </div>

      <div
        style={{
          flex: 1,
          padding: 28,
          display: "flex",
          flexDirection: "column",
          gap: 24,
          background: C.bg,
        }}
      >
        <DetailCard label="Name">
          <EditableText
            value={experiment.name}
            readOnly={locked}
            onChange={(v) => onUpdate({ name: v })}
            placeholder="smoke-test"
            style={{
              fontSize: 20,
              fontFamily: F.sans,
              fontWeight: 600,
              color: C.text,
              letterSpacing: "-0.02em",
            }}
          />
        </DetailCard>

        <DetailCard label="Description">
          <EditableText
            value={experiment.description}
            readOnly={locked}
            onChange={(v) => onUpdate({ description: v })}
            placeholder="What this experiment verifies"
            style={{ fontSize: 13, fontFamily: F.sans, color: C.text }}
          />
        </DetailCard>

        <div>
          <div style={{ ...S_SECTION_LABEL_SMALL, marginBottom: 8 }}>Command</div>
          <div
            style={{
              background: C.surface,
              borderRadius: 9,
              padding: "12px 16px",
              display: "flex",
              alignItems: "center",
              gap: 10,
              border: `1px solid ${C.border}`,
            }}
          >
            <span
              style={{
                fontFamily: F.mono,
                fontSize: 13,
                color: C.textMuted,
                flexShrink: 0,
                userSelect: "none",
              }}
            >
              $
            </span>
            <EditableText
              value={experiment.command}
              readOnly={locked}
              onChange={(v) => onUpdate({ command: v })}
              placeholder="pytest tests/smoke -q"
              style={{ fontSize: 13, fontFamily: F.mono, color: C.text, flex: 1 }}
              inputStyle={{ color: C.text, borderBottomColor: C.accent }}
            />
          </div>
        </div>

        <PlaceholderSection label="Results" placeholder="no runs yet" />
        <PlaceholderSection label="Traces" placeholder="none attached" />
      </div>
    </div>
  );
}

function DetailCard({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 9,
        padding: "16px 18px",
      }}
    >
      <div style={{ ...S_SECTION_LABEL_SMALL, marginBottom: 10 }}>{label}</div>
      {children}
    </div>
  );
}

function PlaceholderSection({ label, placeholder }: { label: string; placeholder: string }) {
  return (
    <div>
      <div style={{ ...S_SECTION_LABEL_SMALL, marginBottom: 8 }}>{label}</div>
      <div
        style={{
          border: `1px dashed ${C.border}`,
          borderRadius: 9,
          padding: "22px 20px",
          color: C.textMuted,
          fontSize: 12,
          fontFamily: F.mono,
          textAlign: "center",
          background: C.surface,
        }}
      >
        {placeholder}
      </div>
    </div>
  );
}

function DeleteButton({ onClick }: { onClick: () => void }) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered ? "#fef2f2" : "none",
        border: `1px solid ${hovered ? "#fecaca" : "transparent"}`,
        cursor: "pointer",
        color: hovered ? "#dc2626" : C.textMuted,
        fontSize: 12,
        fontFamily: F.sans,
        padding: "4px 8px",
        borderRadius: 5,
        display: "flex",
        alignItems: "center",
        gap: 5,
        transition: "color 0.12s, border-color 0.12s",
      }}
    >
      {Ic.x(12)}
      Delete
    </button>
  );
}
