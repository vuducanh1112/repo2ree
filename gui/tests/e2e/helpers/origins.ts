/**
 * Small public Git origin used by the live acquisition/reproduction tests.
 *
 * Keep an override for forks and local experiments. The URL must be reachable
 * from the provisioned workbench container, so a caller cannot generally use
 * localhost here.
 */
export const E2E_GIT_ORIGIN_URL =
  process.env.E2E_GIT_ORIGIN_URL ?? "https://github.com/vuducanh1112/ree-e2e-fixture.git";
