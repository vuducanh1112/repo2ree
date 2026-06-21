import type { RuntimeEntry, RuntimeEntryKind } from "@core/ree/ReeSpec";
import { C, F } from "@shell/ui/theme/theme";

const ENTRY_KINDS: { kind: RuntimeEntryKind; label: string; desc: string; soon?: boolean }[] = [
  { kind: "docker", label: "Docker", desc: "Spin up the runtime container image" },
  {
    kind: "native",
    label: "Native / venv",
    desc: "Run directly on the workbench (with optional activate script)",
  },
  {
    kind: "singularity",
    label: "Singularity",
    desc: "Singularity/Apptainer container",
    soon: true,
  },
  { kind: "vm", label: "VM", desc: "Virtual machine substrate", soon: true },
];

// Picks the runtime substrate (`ree.runtime_entry`) — how the workbench enters
// the runtime. Shared by Test Activation and the Runtime environment page. The
// accent colour lets each host tint it to its own shell.
export function SubstratePicker({
  entry,
  accent,
  onChange,
}: {
  entry: RuntimeEntry;
  accent: string;
  onChange: (next: RuntimeEntry) => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {ENTRY_KINDS.map(({ kind, label, desc, soon }) => {
        const active = entry.kind === kind;
        return (
          <button
            key={kind}
            type="button"
            disabled={!!soon}
            onClick={() => {
              if (soon) return;
              if (kind === "native")
                onChange({
                  kind: "native",
                  activate: entry.kind === "native" ? entry.activate : "",
                });
              else if (kind === "docker") onChange({ kind: "docker" });
              else if (kind === "singularity") onChange({ kind: "singularity", sif: "" });
              else onChange({ kind: "vm", host: "" });
            }}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              padding: "10px 12px",
              borderRadius: 8,
              border: `1.5px solid ${active ? accent : C.border}`,
              background: active ? `${accent}10` : C.surface,
              cursor: soon ? "not-allowed" : "pointer",
              opacity: soon ? 0.5 : 1,
              textAlign: "left",
            }}
          >
            <div
              style={{
                width: 14,
                height: 14,
                borderRadius: "50%",
                border: `2px solid ${active ? accent : C.border}`,
                background: active ? accent : "transparent",
                marginTop: 2,
                flexShrink: 0,
              }}
            />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: C.text, fontFamily: F.sans }}>
                {label}
                {soon && (
                  <span style={{ marginLeft: 6, fontSize: 10, color: C.textMid, fontWeight: 400 }}>
                    coming soon
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, color: C.textMid, fontFamily: F.sans, marginTop: 2 }}>
                {desc}
              </div>
            </div>
          </button>
        );
      })}

      {entry.kind === "native" && (
        <div style={{ marginTop: 4 }}>
          <label
            htmlFor="native-activate"
            style={{ fontSize: 11, fontWeight: 600, color: C.textMid, fontFamily: F.sans }}
          >
            Activate script (optional)
          </label>
          <input
            id="native-activate"
            type="text"
            value={entry.activate}
            placeholder="e.g. source .venv/bin/activate"
            onChange={(e) => onChange({ kind: "native", activate: e.target.value })}
            style={{
              display: "block",
              marginTop: 4,
              width: "100%",
              padding: "6px 10px",
              fontSize: 12,
              fontFamily: F.mono,
              border: `1px solid ${C.border}`,
              borderRadius: 6,
              background: C.surface,
              color: C.text,
              boxSizing: "border-box",
            }}
          />
        </div>
      )}
    </div>
  );
}
