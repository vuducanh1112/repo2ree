import { Ic } from "../../../shared/components/Icon";
import {
  C,
  F,
  hoverColor,
  S_FIELD_TIP_CARD_BLOCK,
  S_FIELD_TIP_CARD_BLOCK_LABEL,
  S_FIELD_TIP_CARD_COMMANDS_LABEL,
  S_SECTION_LABEL,
} from "../../../theme/theme";
import { FIELD_META } from "../../fieldTips/fieldMeta";

interface FieldTipCardProps {
  fieldKey: string;
  onDismiss: () => void;
}

export function FieldTipCard({ fieldKey, onDismiss }: FieldTipCardProps) {
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
