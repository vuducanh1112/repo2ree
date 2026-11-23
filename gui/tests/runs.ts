import { appendFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { type Page, type Response, test } from "@playwright/test";
import type { components } from "../src/shell/infra/api/generated/openapi";

export interface RunWatch {
  stallMs: number;
  budgetMs: number;
}

const INSTANT_RUN: RunWatch = { stallMs: 30_000, budgetMs: 180_000 };

export const NETWORK_RUN: RunWatch = { stallMs: 120_000, budgetMs: 1_200_000 };

function projectRunWatch(): RunWatch {
  return test.info().project.metadata?.runWatch === "instant" ? INSTANT_RUN : NETWORK_RUN;
}

export function quiet(watch: RunWatch = projectRunWatch()): RunWatch {
  return { ...watch, stallMs: Math.max(watch.stallMs, 300_000) };
}

interface StartedRun {
  apiBase: string;
  reeId: string;
  runId: string;
}

type RunSummary = components["schemas"]["RunSummary"];
type RunLogPage = components["schemas"]["RunLogPage"];

const TERMINAL = new Set(["succeeded", "failed", "canceled"]);
const POLL_MS = 500;
const TAIL_LINES = 20;

async function runStartedBy(response: Response): Promise<StartedRun | null> {
  if (response.request().method() !== "POST" || !response.ok()) return null;
  const url = response.url();
  if (!new URL(url).pathname.startsWith("/api/v1/rees")) return null;
  const body = (await response.json().catch(() => null)) as Partial<RunSummary> | null;
  if (!body || typeof body.run_id !== "string" || typeof body.ree_id !== "string") return null;
  return { apiBase: url.slice(0, url.indexOf("/api/v1/")), reeId: body.ree_id, runId: body.run_id };
}

export class StartedRuns {
  private readonly started: StartedRun[] = [];
  private readonly waiting: ((run: StartedRun) => void)[] = [];
  private readonly listener = (response: Response) => {
    void runStartedBy(response).then((run) => {
      if (run === null) return;
      const waiter = this.waiting.shift();
      if (waiter) waiter(run);
      else this.started.push(run);
    });
  };

  constructor(private readonly page: Page) {
    page.on("response", this.listener);
  }

  async next(timeoutMs: number = projectRunWatch().stallMs): Promise<StartedRun> {
    const ready = this.started.shift();
    if (ready) return ready;
    return new Promise<StartedRun>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.waiting.splice(this.waiting.indexOf(waiter), 1);
        reject(new Error(`no run started within ${Math.round(timeoutMs / 1000)}s`));
      }, timeoutMs);
      const waiter = (run: StartedRun) => {
        clearTimeout(timer);
        resolve(run);
      };
      this.waiting.push(waiter);
    });
  }

  stop() {
    this.page.off("response", this.listener);
  }
}

function recordRun(record: Record<string, string | number>) {
  const info = test.info();
  info.annotations.push({ type: "run", description: JSON.stringify(record) });
  mkdirSync(info.outputDir, { recursive: true });
  appendFileSync(path.join(info.outputDir, "runs.ndjson"), `${JSON.stringify(record)}\n`);
}

export interface SettleOptions {
  watch?: RunWatch;
  succeed?: boolean;
}

export async function settleRun(
  page: Page,
  run: StartedRun,
  { watch = projectRunWatch(), succeed = false }: SettleOptions = {},
): Promise<RunSummary> {
  const base = `${run.apiBase}/api/v1/rees/${run.reeId}/runs/${run.runId}`;
  const started = performance.now();
  let lastProgress = started;
  let longestSilence = 0;
  let status = "";
  let cursor: string | null = null;
  const tail: string[] = [];

  const failure = (reason: string) =>
    new Error(
      `run ${run.runId} ${reason}; last log lines:\n${tail.length ? tail.join("\n") : "(none)"}`,
    );

  for (;;) {
    const now = performance.now();
    const summary = (await (await page.request.get(base)).json()) as RunSummary;
    const logs = (await (
      await page.request.get(`${base}/logs`, cursor === null ? {} : { params: { cursor } })
    ).json()) as RunLogPage;
    if (logs.entries.length || summary.status !== status) {
      longestSilence = Math.max(longestSilence, now - lastProgress);
      lastProgress = now;
    }
    for (const entry of logs.entries) {
      tail.push(`[${entry.level}] ${entry.message}`);
      if (tail.length > TAIL_LINES) tail.shift();
    }
    cursor = logs.next_cursor ?? cursor;
    status = summary.status;

    if (TERMINAL.has(status)) {
      recordRun({
        operation: summary.operation,
        status,
        seconds: Math.round((now - started) / 1000),
        longestSilenceSeconds: Math.round(longestSilence / 1000),
        stallSeconds: Math.round(watch.stallMs / 1000),
      });
      if (succeed && status !== "succeeded") {
        throw failure(
          `${summary.operation} ${status}: ${summary.failure?.message ?? "no failure recorded"}`,
        );
      }
      return summary;
    }
    if (now - lastProgress > watch.stallMs) {
      throw failure(
        `${summary.operation} logged nothing for ${Math.round(watch.stallMs / 1000)}s while ${status}`,
      );
    }
    if (now - started > watch.budgetMs) {
      throw failure(
        `${summary.operation} still ${status} after ${Math.round(watch.budgetMs / 1000)}s`,
      );
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }
}

async function startRun(page: Page, action: () => Promise<unknown>): Promise<StartedRun> {
  const runs = new StartedRuns(page);
  try {
    await action();
    return await runs.next();
  } finally {
    runs.stop();
  }
}

export async function runToEnd(
  page: Page,
  action: () => Promise<unknown>,
  options: SettleOptions = {},
): Promise<RunSummary> {
  return settleRun(page, await startRun(page, action), options);
}
