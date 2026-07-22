import type { ScriptInferenceOutcome } from "@shell/data/scriptInference/mutations";
import { renderDecisionDiagram, renderDecisionTrace } from "@shell/data/scriptInference/traceAscii";
import { Ic } from "@shell/ui/shared/components/Icon";
import { lgColors, lgGlassButton } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import type { UseMutationResult } from "@tanstack/react-query";
import { useCallback, useState } from "react";

type Tone = "ok" | "info" | "warn" | "error";
interface Status {
  tone: Tone;
  message: string;
}

function toneColor(tone: Tone): string {
  if (tone === "error") return lgColors.danger;
  if (tone === "warn") return lgColors.warning;
  if (tone === "info") return lgColors.suggestionText;
  return lgColors.success;
}

interface Props {
  // Any generate mutation: build, activation, or experiment. They all resolve to
  // the same outcome, so this one control renders every target.
  generate: UseMutationResult<ScriptInferenceOutcome, Error, void>;
  // Load a generated body into the editor (wire to the editor's externalEdit).
  onLoad: (body: string) => void;
  // What the button generates, e.g. "build script" / "activation script".
  noun: string;
  // An extra sentence appended to the not-inferred message, e.g. the concrete
  // evidence a build target was looking for. Omitted for run scaffolds.
  notInferredHint?: string;
  disabled?: boolean;
}

// A "Generate from repository" affordance: it infers a script from the
// repository / built runtime and loads it into the editor (nothing is saved),
// then explains the outcome and, collapsibly, the decision graph. One control
// for every target so build, activation, and experiments behave identically.
export function GenerateScriptControl({
  generate,
  onLoad,
  noun,
  notInferredHint,
  disabled = false,
}: Props) {
  const [status, setStatus] = useState<Status | null>(null);
  const [traceText, setTraceText] = useState<string | null>(null);

  const handleGenerate = useCallback(() => {
    setStatus(null);
    generate.mutate(undefined, {
      onSuccess: ({ generation, trace, dag }) => {
        setTraceText(
          dag && trace
            ? renderDecisionDiagram(dag, trace)
            : trace
              ? renderDecisionTrace(trace)
              : null,
        );
        if (generation.status === "not_inferred") {
          const hint = notInferredHint ? ` ${notInferredHint}` : "";
          const why =
            generation.blockingMessages.length > 0
              ? ` ${generation.blockingMessages.join(" ")}`
              : "";
          setStatus({
            tone: "warn",
            message: `No ${noun} could be inferred yet.${hint}${why} See the decision graph below.`,
          });
          return;
        }
        onLoad(generation.script.body);
        const parts = [`Loaded a generated ${noun} (${generation.script.ruleId}).`];
        if (generation.script.alternativeCount > 1) {
          parts.push(
            `${generation.script.alternativeCount} alternatives were available — review before saving.`,
          );
        }
        for (const message of generation.script.blockingMessages) parts.push(message);
        parts.push("Review it, then save to keep it.");
        // A strategy that warrants confirmation reads as advisory (info); an
        // automatically-allowed one as a clean success (ok).
        const tone: Tone =
          generation.script.application === "confirmation_required" ? "info" : "ok";
        setStatus({ tone, message: parts.join(" ") });
      },
      onError: (error) => {
        setTraceText(null);
        setStatus({
          tone: "error",
          message: `Generation failed: ${error instanceof Error ? error.message : String(error)}`,
        });
      },
    });
  }, [generate, onLoad, noun, notInferredHint]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={handleGenerate}
          disabled={disabled || generate.isPending}
          title={`Infer a ${noun} from the built runtime. It loads into the editor below; nothing is saved until you save.`}
          style={{
            ...lgGlassButton(),
            padding: "6px 12px",
            fontSize: 12,
            fontWeight: 700,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            opacity: disabled || generate.isPending ? 0.55 : 1,
            cursor: disabled || generate.isPending ? "not-allowed" : "pointer",
          }}
        >
          {generate.isPending ? Ic.loader(14) : Ic.fileCode(14)}
          {generate.isPending ? "Generating…" : "Generate from repository"}
        </button>
        {status && (
          <span style={{ fontSize: 12, color: toneColor(status.tone) }}>{status.message}</span>
        )}
      </div>
      {traceText && (
        <details>
          <summary
            style={{ cursor: "pointer", fontSize: 12, fontWeight: 700, color: lgColors.textMuted }}
          >
            Decision graph
          </summary>
          <pre
            style={{
              margin: "8px 0 0",
              padding: "10px 12px",
              overflowX: "auto",
              borderRadius: 8,
              background: "rgba(15, 23, 42, 0.04)",
              border: "1px solid rgba(125, 211, 252, 0.35)",
              fontFamily: F.mono,
              fontSize: 11.5,
              lineHeight: 1.5,
              color: lgColors.textMid,
              whiteSpace: "pre",
            }}
          >
            {traceText}
          </pre>
        </details>
      )}
    </div>
  );
}
