import { execFile, execFileSync } from "node:child_process";
import { promisify } from "node:util";
import { test } from "@playwright/test";

const run = promisify(execFile);

const REVIEWER_MACHINE =
  "docker.io/library/docker:29-dind@sha256:66d292e5c26bd33a6f6f61cacb880de2186339a524ecba1ce098dbbaceed6515";
const DAEMON_START_MS = 60_000;
const REPRODUCTION_TIMEOUT_MS = 10 * 60_000;

export async function reproduceOffline(archive: string): Promise<string> {
  const machine = `ree-offline-${process.pid}-${Date.now()}`;
  execFileSync("docker", [
    ...["run", "-d", "--privileged", "--network", "none", "--name", machine],
    ...["-e", "DOCKER_TLS_CERTDIR=", REVIEWER_MACHINE],
  ]);
  let output = "";
  try {
    await waitForDaemon(machine);
    execFileSync("docker", ["cp", archive, `${machine}:/root/ree.zip`]);
    const reproduce = "cd /root && unzip -q ree.zip && cd ree && sh run.sh all";
    try {
      const { stdout, stderr } = await run("docker", ["exec", machine, "sh", "-c", reproduce], {
        timeout: REPRODUCTION_TIMEOUT_MS,
        maxBuffer: 64 * 1024 * 1024,
      });
      output = stdout + stderr;
    } catch (error) {
      const failed = error as { stdout?: string; stderr?: string };
      output = `${failed.stdout ?? ""}${failed.stderr ?? ""}`;
      throw new Error(`run.sh all failed offline:\n${output.slice(-4000)}`);
    }
    return output;
  } finally {
    await test
      .info()
      .attach("offline-reproduction.log", { body: output, contentType: "text/plain" });
    execFileSync("docker", ["rm", "-f", "-v", machine], { stdio: "ignore" });
  }
}

async function waitForDaemon(machine: string) {
  const deadline = performance.now() + DAEMON_START_MS;
  for (;;) {
    try {
      await run("docker", ["exec", machine, "docker", "info"]);
      return;
    } catch (error) {
      if (performance.now() > deadline)
        throw new Error(`the offline machine's Docker never started: ${error}`);
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }
}
