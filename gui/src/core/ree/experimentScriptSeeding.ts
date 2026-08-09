/**
 * Where a named experiment's run script must exist before it can be declared.
 *
 * A declaration carries the script's identity — path, digest and size — read
 * off authored bytes, so the backend refuses to declare an experiment whose run
 * script is not authored yet, and rejects the whole definition patch with it.
 * The build and activation scripts never hit this because their paths are fixed
 * and seeded at REE creation; an experiment's path is derived from its name, so
 * nothing can seed it until the author supplies one — which makes seeding the
 * client's job, from the template the backend serves for exactly this purpose.
 */
interface ExperimentRunScriptSeed {
  /** Authored file to carry over, when a rename moved the destination. */
  fromPath?: string;
  toPath: string;
  content: string;
}

interface ExperimentRunScriptSeedInput {
  /** The experiment's name as authored, untrimmed. */
  name: string;
  /** The run-script path already declared on the experiment, or "" if none. */
  declaredPath: string;
  /** Where the name says the run script belongs now. */
  targetPath: string;
  /** Whether the workspace already holds a file at ``targetPath``. */
  targetExists: boolean;
  /** Content at ``declaredPath``, or null when nothing is authored there. */
  declaredContent: string | null;
  /** The backend's starter template, used when there is nothing to carry over. */
  templateBody: string;
}

/**
 * The write that makes a named experiment declarable, or null when none is
 * needed. Renaming carries the authored script to the new path rather than
 * reseeding the template over it — a rename must not silently discard the
 * author's script. Pure.
 */
export function planExperimentRunScriptSeed(
  input: ExperimentRunScriptSeedInput,
): ExperimentRunScriptSeed | null {
  // An unnamed experiment has no destination to seed: the path is derived from
  // the name, and the backend cannot declare it either way.
  if (input.name.trim() === "") return null;
  if (input.targetExists) return null;
  const renamed = input.declaredPath !== "" && input.declaredPath !== input.targetPath;
  const carried = renamed ? input.declaredContent : null;
  return {
    ...(carried !== null ? { fromPath: input.declaredPath } : {}),
    toPath: input.targetPath,
    content: carried ?? input.templateBody,
  };
}
