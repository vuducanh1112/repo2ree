import type React from "react";
import { Ic } from "../../../../components/Icon";
import { FIELD_META } from "../../../../constants/fieldMeta";
import {
  C,
  F,
  hoverColor,
  S_FIELD_ROW_BASE,
  S_FIELD_ROW_CONTENT,
  S_FIELD_ROW_DESC,
  S_FIELD_ROW_HEAD,
  S_FIELD_ROW_LABEL_BASE,
  S_FIELD_ROW_REQUIRED_BADGE,
  S_FIELD_TIP_CARD_BLOCK,
  S_FIELD_TIP_CARD_BLOCK_LABEL,
  S_FIELD_TIP_CARD_COMMANDS_LABEL,
  S_SECTION_LABEL,
} from "../../../../constants/theme";
import { triggerOnEnterOrSpace } from "../../../../utils";

function tipTargetChip(active: boolean, idleLabel = "Click for tips"): React.ReactNode {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: 10,
        fontWeight: 700,
        fontFamily: F.sans,
        color: active ? C.accent : C.textMuted,
        background: active ? C.accentBg : C.surfaceAlt,
        border: `1px solid ${active ? C.accentBorder : C.border}`,
        borderRadius: 99,
        padding: "1px 7px",
        letterSpacing: 0.2,
      }}
    >
      {Ic.info(10)} {active ? "Tips open" : idleLabel}
    </span>
  );
}

export function descToTwoTierTips(desc: string): string[] {
  const text = (desc || "").trim();
  if (!text) return [];
  const firstSentenceEnd = text.indexOf(".");
  if (firstSentenceEnd === -1 || firstSentenceEnd === text.length - 1) return [text];
  const first = text.slice(0, firstSentenceEnd + 1).trim();
  const second = text.slice(firstSentenceEnd + 1).trim();
  return second ? [first, second] : [first];
}

interface FieldRowProps {
  fieldKey: string;
  required?: boolean;
  children: React.ReactNode;
  locked?: boolean;
  onFocus?: () => void;
  active?: boolean;
}
export function FieldRow({ fieldKey, required, children, locked, onFocus, active }: FieldRowProps) {
  const meta = FIELD_META[fieldKey] || { label: fieldKey, desc: "" };
  const tipEnabled = !!onFocus;
  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: section container intentionally acts as full-surface tip target.
    <div
      id={`field-${fieldKey}`}
      onClick={tipEnabled ? () => onFocus?.() : undefined}
      role={tipEnabled ? "button" : undefined}
      tabIndex={tipEnabled ? 0 : undefined}
      onKeyDown={(event) => {
        if (!tipEnabled) return;
        triggerOnEnterOrSpace(event, () => onFocus?.());
      }}
      style={{
        ...S_FIELD_ROW_BASE,
        background: active ? `${C.accentBg}75` : "transparent",
        cursor: tipEnabled ? "pointer" : "default",
        borderLeftColor: active ? C.accent : "transparent",
        boxShadow: active ? `inset 0 0 0 1px ${C.accentBorder}` : "none",
      }}
    >
      <div>
        <div style={S_FIELD_ROW_HEAD}>
          <span
            style={{
              ...S_FIELD_ROW_LABEL_BASE,
              color: active ? C.accent : C.text,
            }}
          >
            {meta.label}
          </span>
          {tipEnabled && tipTargetChip(!!active)}
          {required && <span style={S_FIELD_ROW_REQUIRED_BADGE}>required</span>}
          {locked && fieldKey !== "swhid" && (
            <span
              style={{
                fontSize: 11,
                color: C.textMuted,
                fontFamily: F.sans,
                background: C.surfaceAlt,
                border: `1px solid ${C.border}`,
                borderRadius: 3,
                padding: "1px 4px",
              }}
            >
              locked
            </span>
          )}
        </div>
        <p style={S_FIELD_ROW_DESC}>{meta.desc}</p>
      </div>
      <div style={S_FIELD_ROW_CONTENT}>{children}</div>
    </div>
  );
}

interface FieldSectionProps {
  title: string;
  icon: React.ReactNode;
  subtitle?: string;
  children: React.ReactNode;
  filledCount: number;
  totalCount: number;
}
export function FieldSection({
  title,
  icon,
  subtitle,
  children,
  filledCount,
  totalCount,
}: FieldSectionProps) {
  const allFilled = filledCount === totalCount && totalCount > 0;
  const someFilled = filledCount > 0;
  const pct = totalCount > 0 ? Math.round((filledCount / totalCount) * 100) : 0;
  return (
    <div
      style={{
        ...{
          background: C.surface,
          borderRadius: 10,
          overflow: "hidden",
          transition: "border-color 0.3s",
          boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        },
        border: `1px solid ${allFilled ? "#22c55e40" : C.border}`,
      }}
    >
      <div
        style={{
          ...{
            padding: "11px 20px",
            display: "flex",
            alignItems: "center",
            gap: 8,
            transition: "background 0.3s",
          },
          borderBottom: `1px solid ${allFilled ? "#22c55e30" : C.border}`,
          background: allFilled ? "#f0fdf4" : "#fafbfd",
        }}
      >
        <div
          style={{
            ...{
              width: 3,
              height: 16,
              borderRadius: 99,
              flexShrink: 0,
              transition: "background 0.3s",
            },
            background: allFilled ? "#22c55e" : someFilled ? "#f59e0b" : C.borderMid,
          }}
        />
        <span
          style={{
            ...{
              display: "flex",
            },
            color: allFilled ? "#16a34a" : C.textMuted,
          }}
        >
          {icon}
        </span>
        <span
          style={{
            ...{
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: 1,
              textTransform: "uppercase",
              fontFamily: F.sans,
            },
            color: allFilled ? "#15803d" : C.text,
          }}
        >
          {title}
        </span>
        {subtitle && (
          <span
            style={{
              fontSize: 12,
              color: C.textMuted,
              fontWeight: 400,
              textTransform: "none",
              letterSpacing: 0,
            }}
          >
            — {subtitle}
          </span>
        )}
        <div
          style={{
            flex: 1,
          }}
        />
        {totalCount > 0 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <div
              style={{
                width: 40,
                height: 3,
                borderRadius: 99,
                background: C.border,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${pct}%`,
                  height: "100%",
                  background: allFilled ? "#22c55e" : someFilled ? "#f59e0b" : C.borderMid,
                  borderRadius: 99,
                  transition: "width 0.4s",
                }}
              />
            </div>
            <span
              style={{
                ...{
                  fontSize: 11,
                  fontFamily: F.mono,
                  fontWeight: 600,
                },
                color: allFilled ? "#16a34a" : someFilled ? "#92400e" : C.textMuted,
              }}
            >
              {filledCount}/{totalCount}
            </span>
          </div>
        )}
      </div>
      <div
        style={{
          padding: "0 20px",
        }}
      >
        {children}
      </div>
    </div>
  );
}

interface FieldTipCardProps {
  fieldKey: string;
  onDismiss: () => void;
}
function FieldTipCard({ fieldKey, onDismiss }: FieldTipCardProps) {
  const meta = FIELD_META[fieldKey];
  if (!meta) return null;
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
        padding: 16,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 10,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 7,
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: C.accent,
            }}
          />
          <span
            style={{
              ...S_SECTION_LABEL,
              letterSpacing: 1.1,
              color: C.accent,
            }}
          >
            Field guide
          </span>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          style={{
            fontSize: 11,
            fontFamily: F.sans,
            color: C.textMuted,
            background: C.surfaceAlt,
            border: `1px solid ${C.border}`,
            borderRadius: 6,
            padding: "4px 8px",
            cursor: "pointer",
          }}
          {...hoverColor(C.text, C.textMuted)}
        >
          {Ic.x(13)}
        </button>
      </div>

      <div
        style={{
          fontSize: 15,
          fontWeight: 700,
          color: C.text,
          marginBottom: 4,
        }}
      >
        {meta.label}
      </div>
      <p
        style={{
          fontSize: 13,
          color: C.textMid,
          lineHeight: 1.6,
          margin: "0 0 14px",
        }}
      >
        {meta.desc}
      </p>

      {meta.example && (
        <div style={S_FIELD_TIP_CARD_BLOCK}>
          <div style={S_FIELD_TIP_CARD_BLOCK_LABEL}>Example</div>
          <div
            style={{
              background: C.surfaceAlt,
              border: `1px solid ${C.border}`,
              borderRadius: 6,
              padding: "9px 12px",
              fontFamily: F.mono,
              fontSize: 13,
              color: C.accent,
              wordBreak: "break-all",
            }}
          >
            {meta.example}
          </div>
        </div>
      )}

      {meta.format && (
        <div style={S_FIELD_TIP_CARD_BLOCK}>
          <div style={S_FIELD_TIP_CARD_BLOCK_LABEL}>Format</div>
          <p
            style={{
              fontSize: 13,
              color: C.textMid,
              lineHeight: 1.6,
              margin: 0,
              fontFamily: F.mono,
            }}
          >
            {meta.format}
          </p>
        </div>
      )}

      {meta.howTo && (
        <div style={S_FIELD_TIP_CARD_BLOCK}>
          <div style={S_FIELD_TIP_CARD_BLOCK_LABEL}>How to get this</div>
          <pre
            style={{
              ...{
                fontSize: 13,
                color: C.textMid,
                lineHeight: 1.65,
                margin: 0,
                whiteSpace: "pre-wrap",
              },
              fontFamily: meta.howTo.includes("\n") ? F.mono : "inherit",
            }}
          >
            {meta.howTo}
          </pre>
        </div>
      )}

      {meta.toolCommands && meta.toolCommands.length > 0 && (
        <div style={S_FIELD_TIP_CARD_BLOCK}>
          <div style={S_FIELD_TIP_CARD_COMMANDS_LABEL}>Commands</div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            {meta.toolCommands.map((tc) => (
              <div key={`${tc.label}:${tc.cmd}`}>
                <div
                  style={{
                    fontSize: 11,
                    color: C.textMuted,
                    fontFamily: F.sans,
                    marginBottom: 4,
                  }}
                >
                  {tc.label}
                </div>
                <div
                  style={{
                    background: "#0f172a",
                    borderRadius: 6,
                    padding: "10px 12px",
                    fontFamily: F.mono,
                    fontSize: 13,
                    color: "#94d2bd",
                    wordBreak: "break-all",
                    lineHeight: 1.6,
                  }}
                >
                  {tc.cmd}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {meta.tools && meta.tools.length > 0 && (
        <div>
          <div style={S_FIELD_TIP_CARD_COMMANDS_LABEL}>Tools</div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 6,
            }}
          >
            {meta.tools.map((t) => (
              <a
                key={t.url}
                href={t.url}
                target="_blank"
                rel="noreferrer"
                style={{
                  fontSize: 13,
                  fontFamily: F.sans,
                  color: C.accent,
                  background: C.accentBg,
                  border: `1px solid ${C.accentBorder}`,
                  borderRadius: 5,
                  padding: "4px 10px",
                  textDecoration: "none",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                {Ic.link(11)} {t.label}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface FieldTipsSidebarProps {
  focusedField: string | null;
  onFocusField?: (field: string) => void;
  onClear: () => void;
  tipFields?: string[];
  emptyMessage?: string;
  generalTips?: string[];
  generalTitle?: string;
}
export function FieldTipsSidebar({
  focusedField,
  onFocusField,
  onClear,
  tipFields,
  emptyMessage,
  generalTips = [],
  generalTitle = "Step Purpose",
}: FieldTipsSidebarProps) {
  const activeField =
    focusedField && (!tipFields || tipFields.includes(focusedField)) ? focusedField : null;
  const showFieldPicker = !!(tipFields && tipFields.length > 0 && onFocusField);
  const emptyText =
    emptyMessage ||
    "Click any field — here or in the status bar above — to see examples, format rules, and commands.";
  const workflowTipFields = (tipFields || []).filter((fieldKey) => !!FIELD_META[fieldKey]);

  return (
    <div
      style={{
        width: 296,
        borderLeft: `1px solid ${C.border}`,
        background: C.surface,
        overflowY: "auto",
        padding: 20,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}
    >
      {showFieldPicker && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <div
            style={{
              ...S_SECTION_LABEL,
              letterSpacing: 1.1,
            }}
          >
            Tips
          </div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 6,
            }}
          >
            {(tipFields || []).map((fieldKey) => {
              const isActive = activeField === fieldKey;
              return (
                <button
                  type="button"
                  key={fieldKey}
                  onClick={() => onFocusField(fieldKey)}
                  style={{
                    ...{
                      fontSize: 11,
                      fontFamily: F.sans,
                      fontWeight: 700,
                      letterSpacing: 0.2,
                      borderRadius: 99,
                      padding: "3px 9px",
                      cursor: "pointer",
                    },
                    color: isActive ? C.accent : C.textMid,
                    background: isActive ? C.accentBg : C.surfaceAlt,
                    border: `1px solid ${isActive ? C.accentBorder : C.border}`,
                  }}
                >
                  {FIELD_META[fieldKey]?.label || fieldKey}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {generalTips.length > 0 && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
            }}
          >
            <span
              style={{
                color: C.textMid,
                display: "flex",
              }}
            >
              {Ic.info(13)}
            </span>
            <span
              style={{
                ...S_SECTION_LABEL,
                letterSpacing: 0.8,
                color: C.textMid,
              }}
            >
              {generalTitle}
            </span>
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            {generalTips.map((tip) => (
              <p
                key={tip}
                style={{
                  margin: 0,
                  fontSize: 12,
                  color: C.textMid,
                  lineHeight: 1.55,
                }}
              >
                {tip}
              </p>
            ))}
          </div>
        </div>
      )}

      {activeField ? (
        <FieldTipCard fieldKey={activeField} onDismiss={onClear} />
      ) : workflowTipFields.length > 0 ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 10,
            padding: "12px 13px",
            background: C.accentBg,
            border: `1px solid ${C.accentBorder}`,
            borderRadius: 9,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
            }}
          >
            <span
              style={{
                color: C.accent,
                display: "flex",
              }}
            >
              {Ic.info(13)}
            </span>
            <span
              style={{
                ...S_SECTION_LABEL,
                letterSpacing: 0.8,
                color: C.accent,
              }}
            >
              Workflow tips
            </span>
          </div>
          <p
            style={{
              fontSize: 12,
              color: C.textMid,
              lineHeight: 1.55,
              margin: 0,
            }}
          >
            No field selected. Here are the key tips for this page/workflow:
          </p>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            {workflowTipFields.map((fieldKey) => {
              const meta = FIELD_META[fieldKey];
              return (
                <button
                  type="button"
                  key={fieldKey}
                  onClick={() => onFocusField?.(fieldKey)}
                  style={{
                    ...{
                      textAlign: "left",
                      padding: "8px 10px",
                      borderRadius: 8,
                      border: `1px solid ${C.accentBorder}`,
                      background: C.surface,
                      display: "flex",
                      flexDirection: "column",
                      gap: 3,
                    },
                    cursor: onFocusField ? "pointer" : "default",
                  }}
                >
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: C.text,
                      fontFamily: F.sans,
                    }}
                  >
                    {meta?.label || fieldKey}
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      color: C.textMuted,
                      lineHeight: 1.45,
                    }}
                  >
                    {meta?.desc || ""}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 8,
            padding: "12px 13px",
            background: C.accentBg,
            border: `1px solid ${C.accentBorder}`,
            borderRadius: 9,
          }}
        >
          <span
            style={{
              color: C.accent,
              flexShrink: 0,
              marginTop: 1,
            }}
          >
            {Ic.info(13)}
          </span>
          <p
            style={{
              fontSize: 13,
              color: C.textMid,
              lineHeight: 1.6,
              margin: 0,
            }}
          >
            {emptyText}
          </p>
        </div>
      )}
    </div>
  );
}
