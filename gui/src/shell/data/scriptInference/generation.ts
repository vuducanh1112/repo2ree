export type ScriptApplication = "automatic_allowed" | "confirmation_required" | "unavailable";

export interface GeneratedScript {
  body: string;
  ruleId: string;
  application: ScriptApplication;
  alternativeCount: number;
  blockingMessages: string[];
  experimentEnvironmentPath?: string;
}

export type ScriptGeneration =
  | { status: "generated"; script: GeneratedScript }
  | { status: "not_inferred"; blockingMessages: string[] };
