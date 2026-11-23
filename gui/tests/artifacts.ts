import { join } from "node:path";

const REPO_ROOT = join(__dirname, "..", "..");

const ARTIFACTS_DIR = join(REPO_ROOT, "test-artifacts");

export const FIXTURES_DIR = join(ARTIFACTS_DIR, "fixtures");
