/**
 * Source/runtime/results inclusion is a seal-time choice, not authoring state.
 * These options parameterize the archive build at seal/download time; the
 * settled values are recorded into the session (see the backend's bundle-time
 * `with_packaging`) rather than carried as editable authoring state. Results are
 * the experiments' captured output baselines — always captured locally, bundled
 * only when `includeResults` is set.
 */
export interface InclusionOpts {
  includeSource: boolean;
  includeRuntime: boolean;
  includeResults: boolean;
}
