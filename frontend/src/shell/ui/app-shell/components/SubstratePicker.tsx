import type { RuntimeEntry, RuntimeEntryKind } from "@core/ree/ReeSpec";
import { createDefaultRuntimeEntry } from "@core/ree/ReeSpec";
import { CONTAINER_ENGINES, ENGINE_LABELS } from "@core/ree/runtimeEntryLabels";
import { lgColors, lgInput } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { CommandPlanView } from "./CommandPlanView";

interface KindOption {
  kind: RuntimeEntryKind;
  label: string;
  desc: string;
  soon?: boolean;
}

const ENTRY_KINDS: KindOption[] = [
  {
    kind: "container",
    label: "Container",
    desc: "Spin up the runtime image (Docker, Podman, or Apptainer)",
  },
  {
    kind: "local",
    label: "Local / venv",
    desc: "Run directly on the workbench (with optional activate script)",
  },
  { kind: "vm", label: "VM", desc: "Virtual machine substrate", soon: true },
  {
    kind: "custom",
    label: "Custom",
    desc: "Author-supplied phased driver script",
  },
];

// Picks the runtime substrate (`ree.runtime_entry`) — how the workbench enters
// the runtime. Shared by the Runtime environment and Build Runtime pages. The
// accent colour lets each host tint it to its own shell.
//
// `renderDetail` is the slot rendered under the active substrate. By default it
// is the "what actually runs" command plan (relevant on the runtime page). The
// Build Runtime page overrides it to show the build script that substrate uses,
// so the same picker drives "how it's built" there and "how it's entered" here.
export function SubstratePicker({
  entry,
  accent,
  onChange,
  renderDetail,
}: {
  entry: RuntimeEntry;
  accent: string;
  onChange: (next: RuntimeEntry) => void;
  renderDetail?: (entry: RuntimeEntry) => React.ReactNode;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Runtime substrate"
      style={{ display: "flex", flexDirection: "column", gap: 8 }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: lgColors.textMuted,
          fontFamily: F.sans,
          textTransform: "uppercase",
          letterSpacing: 0.4,
          marginBottom: 2,
        }}
      >
        Choose one substrate
      </div>
      {ENTRY_KINDS.map(({ kind, label, desc, soon }) => {
        const active = entry.kind === kind;
        return (
          <div key={kind} style={{ display: "flex", flexDirection: "column" }}>
            {/* biome-ignore lint/a11y/useSemanticElements: a native radio cannot host
                this rich label/description layout; we expose radiogroup semantics manually. */}
            <button
              type="button"
              role="radio"
              aria-checked={active}
              disabled={!!soon}
              onClick={() => {
                // No-op when already selected: re-defaulting would silently wipe
                // fields this compact UI does not expose (workdir/env/gpus, VM
                // SSH config, custom driver path). Engine has its own button row.
                if (soon || active) return;
                onChange(createDefaultRuntimeEntry(kind, entry));
              }}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 11,
                padding: "11px 13px",
                borderRadius: 8,
                // Active substrate gets a heavier accent border + tint and a soft
                // glow so exactly one option reads as chosen; the rest recede to a
                // flat, muted row that clearly looks unselected (not a checklist).
                border: active ? `2px solid ${accent}` : "1px solid rgba(148, 163, 184, 0.3)",
                background: active ? `${accent}12` : "rgba(248, 250, 252, 0.6)",
                boxShadow: active ? `0 4px 14px ${accent}1f` : "none",
                cursor: soon ? "not-allowed" : "pointer",
                opacity: soon ? 0.5 : 1,
                textAlign: "left",
              }}
            >
              {/* Classic radio dial: hollow ring when unselected, ring + filled
                  inner dot when selected — a single-choice affordance. */}
              <div
                style={{
                  width: 16,
                  height: 16,
                  borderRadius: "50%",
                  border: `2px solid ${active ? accent : "rgba(148, 163, 184, 0.55)"}`,
                  background: lgColors.white,
                  marginTop: 1,
                  flexShrink: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {active && (
                  <div
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: accent,
                    }}
                  />
                )}
              </div>
              <div>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: active ? 700 : 500,
                    color: active ? lgColors.text : lgColors.textMid,
                    fontFamily: F.sans,
                  }}
                >
                  {label}
                  {soon && (
                    <span
                      style={{
                        marginLeft: 6,
                        fontSize: 10,
                        color: lgColors.textMid,
                        fontWeight: 400,
                      }}
                    >
                      coming soon
                    </span>
                  )}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: lgColors.textMuted,
                    fontFamily: F.sans,
                    marginTop: 2,
                  }}
                >
                  {desc}
                </div>
              </div>
            </button>

            {active && entry.kind === "container" && (
              <div style={{ marginTop: 6, paddingLeft: 4 }}>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: lgColors.textMid,
                    fontFamily: F.sans,
                    marginBottom: 4,
                  }}
                >
                  Engine
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  {CONTAINER_ENGINES.map((eng) => (
                    <button
                      key={eng}
                      type="button"
                      onClick={() => onChange({ ...entry, engine: eng })}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 6,
                        border: `1.5px solid ${entry.engine === eng ? accent : "rgba(148, 163, 184, 0.34)"}`,
                        background: entry.engine === eng ? `${accent}18` : lgColors.white,
                        color: lgColors.text,
                        fontSize: 11,
                        fontFamily: F.sans,
                        cursor: "pointer",
                        fontWeight: entry.engine === eng ? 600 : 400,
                      }}
                    >
                      {ENGINE_LABELS[eng]}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {active &&
              (renderDetail ? (
                renderDetail(entry)
              ) : (
                <DefaultSubstrateDetail entry={entry} onChange={onChange} />
              ))}
          </div>
        );
      })}
    </div>
  );
}

// The default detail slot: how the workbench *enters* the runtime — the editable
// enter-config (local activate / custom driver path) plus the read-only command
// plan. Replaced wholesale by `renderDetail` on the Build Runtime page, which
// cares about how the artifact is *built*, not how it is entered.
function DefaultSubstrateDetail({
  entry,
  onChange,
}: {
  entry: RuntimeEntry;
  onChange: (next: RuntimeEntry) => void;
}) {
  return (
    <>
      {entry.kind === "local" && (
        <div style={{ marginTop: 8 }}>
          <label
            htmlFor="local-activate"
            style={{ fontSize: 11, fontWeight: 600, color: lgColors.textMid, fontFamily: F.sans }}
          >
            Activate script (optional)
          </label>
          <input
            id="local-activate"
            type="text"
            value={entry.activate}
            placeholder="e.g. source .venv/bin/activate"
            onChange={(e) => onChange({ ...entry, activate: e.target.value })}
            style={enterConfigInput}
          />
        </div>
      )}

      {entry.kind === "custom" && (
        <div style={{ marginTop: 8 }}>
          <label
            htmlFor="custom-enter-script"
            style={{ fontSize: 11, fontWeight: 600, color: lgColors.textMid, fontFamily: F.sans }}
          >
            Driver script path
          </label>
          <input
            id="custom-enter-script"
            type="text"
            value={entry.enter_script}
            placeholder="e.g. scripts/my-driver or scripts/my-driver/exec"
            onChange={(e) => onChange({ ...entry, enter_script: e.target.value })}
            style={enterConfigInput}
          />
        </div>
      )}

      <CommandPlanView entry={entry} />
    </>
  );
}

const enterConfigInput: React.CSSProperties = {
  ...lgInput(false),
  marginTop: 4,
  padding: "6px 10px",
  fontSize: 12,
  fontFamily: F.mono,
  minHeight: "unset",
  boxSizing: "border-box",
};
