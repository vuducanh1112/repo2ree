import { execFile, execFileSync } from "node:child_process";
import { promisify } from "node:util";
import { test } from "@playwright/test";

const run = promisify(execFile);

/**
 * A machine of the reviewer's: Docker and a POSIX shell, no repo2ree, and no
 * network. The provider's own bench image, pinned by digest, so it is already
 * on the machine running the stack and starts without a pull. It must equal the
 * provider's DEFAULT_IMAGE; provider/tests/test_provider_config.py holds it to it.
 */
const REVIEWER_MACHINE =
  "docker.io/library/docker:29-dind@sha256:66d292e5c26bd33a6f6f61cacb880de2186339a524ecba1ce098dbbaceed6515";
const DAEMON_START_MS = 60_000;
// Loading the sealed runtime and running every step: minutes for a real image.
const REPRODUCTION_TIMEOUT_MS = 10 * 60_000;

/**
 * Reproduce a sealed REE the way REPRODUCING.md tells a reviewer to: unpack the
 * archive and run `sh run.sh all`, on a machine with no repo2ree and no network,
 * so whatever the REE needs must be in the archive. Returns what run.sh printed;
 * it throws when run.sh fails. The output is attached to the test either way.
 */
export async function reproduceOffline(archive: string): Promise<string> {
  const machine = `ree-offline-${process.pid}-${Date.now()}`;
  // An empty TLS directory has the daemon listen on its socket alone: no certificates to make.
  execFileSync("docker", [
    ...["run", "-d", "--privileged", "--network", "none", "--name", machine],
    ...["-e", "DOCKER_TLS_CERTDIR=", REVIEWER_MACHINE],
  ]);
  let output = "";
  try {
    await waitForDaemon(machine);
    // Not /tmp: a tmpfs mounted inside the container, which `docker cp` writes beneath, unseen.
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
  const deadline = Date.now() + DAEMON_START_MS;
  for (;;) {
    try {
      await run("docker", ["exec", machine, "docker", "info"]);
      return;
    } catch (error) {
      if (Date.now() > deadline)
        throw new Error(`the offline machine's Docker never started: ${error}`);
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }
}
