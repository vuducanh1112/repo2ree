import { Ic } from "../../../shared/components/Icon";
import { C, F, hoverBg, hoverIf } from "../../../theme/theme";
export function ScriptPanelWrite(props: {
  editorFilename: string;
  editorContent: string;
  templates: Array<{ key: string; label: string; filename: string; content: string }>;
  templateKey: string;
  isRemoteGit: boolean;
  isGitHub: boolean;
  setEditorFilename: (value: string) => void;
  setEditorContent: (value: string) => void;
  setTemplateKey: (value: string) => void;
  onUseTemplate: () => void;
  onSave: () => void;
}) {
  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 10px",
          borderBottom: `1px solid ${C.border}`,
          background: C.surfaceAlt,
        }}
      >
        <span style={{ color: C.textMuted, display: "flex", flexShrink: 0 }}>
          {Ic.terminal(11)}
        </span>
        <input
          value={props.editorFilename}
          onChange={(event) => props.setEditorFilename(event.target.value)}
          placeholder="filename.sh"
          style={{
            flex: 1,
            border: "none",
            background: "transparent",
            fontSize: 12,
            fontFamily: F.mono,
            color: C.textMid,
            outline: "none",
            minWidth: 0,
          }}
        />
        {props.templates.length > 0 && (
          <>
            <select
              value={props.templateKey}
              onChange={(event) => props.setTemplateKey(event.target.value)}
              style={{
                border: `1.5px solid ${C.border}`,
                borderRadius: 5,
                padding: "4px 8px",
                fontSize: 11,
                fontFamily: F.sans,
                color: C.textMid,
                background: C.surface,
              }}
            >
              {props.templates.map((template) => (
                <option key={template.key} value={template.key}>
                  {template.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={props.onUseTemplate}
              title="Insert selected template into editor"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 10px",
                borderRadius: 5,
                cursor: "pointer",
                border: `1px solid ${C.border}`,
                background: C.surface,
                color: C.textMid,
                fontSize: 11,
                fontWeight: 600,
                fontFamily: F.sans,
                transition: "all 0.13s",
                flexShrink: 0,
                whiteSpace: "nowrap",
              }}
              {...hoverBg(C.surfaceAlt, C.surface)}
            >
              {Ic.plus(12)} Apply template
            </button>
          </>
        )}

        <div style={{ width: 1, height: 16, background: C.border, flexShrink: 0 }} />

        <button
          type="button"
          onClick={props.onSave}
          disabled={!props.editorContent.trim()}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            padding: "4px 10px",
            borderRadius: 5,
            border: `1px solid ${C.accentBorder}`,
            background: C.accentBg,
            fontSize: 11,
            fontWeight: 600,
            fontFamily: F.sans,
            color: C.accent,
            transition: "all 0.13s",
            flexShrink: 0,
            whiteSpace: "nowrap",
            cursor: !props.editorContent.trim() ? "default" : "pointer",
            opacity: !props.editorContent.trim() ? 0.4 : 1,
          }}
          {...hoverIf(!!props.editorContent.trim(), hoverBg("#dbeafe", C.accentBg))}
        >
          {Ic.check(11)} Save to workspace
        </button>
      </div>

      <textarea
        value={props.editorContent}
        onChange={(event) => props.setEditorContent(event.target.value)}
        placeholder={"#!/bin/bash\nset -euo pipefail\n\n# Write your script here..."}
        spellCheck={false}
        style={{
          width: "100%",
          minHeight: 200,
          padding: "10px 14px",
          fontFamily: F.mono,
          fontSize: 12,
          lineHeight: 1.7,
          color: C.text,
          background: C.surface,
          border: "none",
          resize: "vertical",
          outline: "none",
          tabSize: 2,
          display: "block",
        }}
        onKeyDown={(event) => {
          if (event.key === "Tab") {
            event.preventDefault();
            const target = event.currentTarget;
            const selectionStart = target.selectionStart;
            const selectionEnd = target.selectionEnd;
            props.setEditorContent(
              `${props.editorContent.slice(0, selectionStart)}  ${props.editorContent.slice(selectionEnd)}`,
            );
            requestAnimationFrame(() => {
              target.selectionStart = target.selectionEnd = selectionStart + 2;
            });
          }
        }}
      />

      <div
        style={{
          padding: "5px 12px",
          background: C.surfaceAlt,
          borderTop: `1px solid ${C.border}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span style={{ fontSize: 11, fontFamily: F.mono, color: C.textMuted }}>
          {props.editorContent.split("\n").length} lines · Tab = 2 spaces
        </span>
        {props.isRemoteGit && (
          <span
            style={{
              fontSize: 11,
              fontFamily: F.sans,
              color: C.textMuted,
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            {Ic.link(10)}
            <span>{props.isGitHub ? "github.com" : "gitlab.com"} · changes go via PR</span>
          </span>
        )}
      </div>
    </div>
  );
}
