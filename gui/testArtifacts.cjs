const { randomUUID } = require("node:crypto");
const { mkdirSync, writeFileSync } = require("node:fs");
const { resolve, join } = require("node:path");

process.env.REPO2REE_TEST_RUN_ID ??= randomUUID();
process.env.REPO2REE_TEST_RUN_DIR ??= resolve(__dirname, "../test-artifacts");
exports.testRunDir = process.env.REPO2REE_TEST_RUN_DIR;

exports.recordRuntime = (runtime) => {
  const directory = join(exports.testRunDir, runtime);
  mkdirSync(directory, { recursive: true });
  writeFileSync(
    join(directory, "manifest.json"),
    `${JSON.stringify({
      // biome-ignore lint/style/useNamingConvention: Shared Python artifact schema.
      schema_version: 1,
      // biome-ignore lint/style/useNamingConvention: Shared Python artifact schema.
      run_id: process.env.REPO2REE_TEST_RUN_ID,
      created: new Date().toISOString(),
    })}\n`,
  );
};
