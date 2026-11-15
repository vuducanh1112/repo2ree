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
  includeExperimentEnvironment: boolean;
  /** The working environment's OCI image, saved into the archive so a review needs no registry. */
  includeWorkingEnvironment: boolean;
  includeResults: boolean;
}
