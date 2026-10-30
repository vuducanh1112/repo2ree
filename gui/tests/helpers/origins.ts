/**
 * Origins the acquisition and review specs fetch a source from.
 *
 * A source stack serves the fixture project itself (repo2ree_testbed.stack.origins)
 * by git and as a tarball, and names both here through the environment, so these
 * specs need no internet and always fetch the same commit and bytes. The public
 * repository is the fallback only for a stack that serves none (the image-backed
 * suites). Either URL must be reachable from the provisioned workbench container,
 * so a caller cannot generally use localhost here.
 */
export const E2E_GIT_ORIGIN_URL =
  process.env.E2E_GIT_ORIGIN_URL ?? "https://github.com/vuducanh1112/ree-e2e-fixture.git";

/** The same fixture as a `.tar.gz`; only a stack that serves origins has one. */
export const E2E_TARBALL_ORIGIN_URL = process.env.E2E_TARBALL_ORIGIN_URL ?? "";
