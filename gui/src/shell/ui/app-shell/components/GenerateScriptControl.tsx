import type { ScriptInferenceOutcome } from "@shell/data/scriptInference/mutations";
import { renderDecisionDiagram, renderDecisionTrace } from "@shell/data/scriptInference/traceAscii";
import { Button } from "@shell/ui/shared/components/Button";
import { Ic } from "@shell/ui/shared/components/Icon";
import type { UseMutationResult } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import styles from "./GenerateScriptControl.module.css";

type Tone = "ok" | "info" | "warn" | "error";
interface Status {
  tone: Tone;
  message: string;
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
  // Build only: the runtime path the generated script writes to. Fires once per
  // generation, so a page can act on it without an effect that re-runs on every
  // render. Whether to *use* it is the page's call — it knows its own
  // declaration; this control does not.
  onRuntimePath?: (path: string) => void;
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
  onRuntimePath,
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
        if (generation.script.runtimePath) onRuntimePath?.(generation.script.runtimePath);
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
  }, [generate, onLoad, noun, notInferredHint, onRuntimePath]);

  return (
    <div className={styles.control}>
      <div className={styles.row}>
        <Button
          variant="secondary"
          size="small"
          onClick={handleGenerate}
          disabled={disabled || generate.isPending}
          busy={generate.isPending}
          icon={generate.isPending ? Ic.loader(14) : Ic.fileCode(14)}
          title={`Infer a ${noun} from the built runtime. It loads into the editor below; nothing is saved until you save.`}
        >
          {generate.isPending ? "Generating…" : "Generate from repository"}
        </Button>
        {status && (
          <span className={styles.status} data-tone={status.tone}>
            {status.message}
          </span>
        )}
      </div>
      {traceText && (
        <details>
          <summary className={styles.summary}>Decision graph</summary>
          <pre className={styles.trace}>{traceText}</pre>
        </details>
      )}
    </div>
  );
}
