import { useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { C, F, hoverColor } from "../../theme/theme";

interface MetaRowProps {
  label: string;
  value?: string;
  mono?: boolean;
  href?: string;
  color?: string;
}

export function MetaRow({ label, value, mono = false, href, color }: MetaRowProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!value) return;
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    });
  };

  if (!value) {
    return (
      <div
        style={{
          display: "flex",
          gap: 10,
          padding: "7px 0",
          borderBottom: `1px solid ${C.border}`,
          alignItems: "center",
        }}
      >
        <span
          style={{
            width: 130,
            fontSize: 11,
            color: C.textMuted,
            fontFamily: F.sans,
            flexShrink: 0,
          }}
        >
          {label}
        </span>
        <span style={{ fontSize: 11, fontFamily: F.mono, color: C.textMuted, fontStyle: "italic" }}>
          not set
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        padding: "7px 0",
        borderBottom: `1px solid ${C.border}`,
        alignItems: "center",
      }}
    >
      <span
        style={{
          width: 130,
          fontSize: 11,
          color: C.textMuted,
          fontFamily: F.sans,
          flexShrink: 0,
          fontWeight: 500,
        }}
      >
        {label}
      </span>
      <span
        style={{
          flex: 1,
          fontSize: 11,
          fontFamily: mono ? F.mono : F.sans,
          color: color || (mono ? C.accent : C.text),
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            style={{
              color: C.accent,
              display: "inline-flex",
              alignItems: "center",
              gap: 3,
              textDecoration: "none",
            }}
          >
            {value} {Ic.externalLink(10)}
          </a>
        ) : (
          value
        )}
      </span>
      <button
        type="button"
        onClick={handleCopy}
        title="Copy"
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          color: copied ? "#22c55e" : C.textMuted,
          display: "flex",
          padding: 2,
          flexShrink: 0,
          borderRadius: 3,
          transition: "color 0.15s",
        }}
        {...hoverColor(C.textMid, copied ? "#22c55e" : C.textMuted)}
      >
        {copied ? Ic.check(11) : Ic.copy(11)}
      </button>
    </div>
  );
}
