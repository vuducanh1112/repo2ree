import { describe, expect, it } from "vitest";
import { planExperimentRunScriptSeed } from "./experimentScriptSeeding";

const base = {
  name: "python-hello",
  declaredPath: "",
  targetPath: "ree-scripts/experiments/python-hello.sh",
  targetExists: false,
  declaredContent: null,
  templateBody: "#!/usr/bin/env sh\n",
};

describe("planExperimentRunScriptSeed", () => {
  it("seeds the template where a newly named experiment will be declared", () => {
    expect(planExperimentRunScriptSeed(base)).toEqual({
      toPath: "ree-scripts/experiments/python-hello.sh",
      content: "#!/usr/bin/env sh\n",
    });
  });

  it("has nothing to do once the script is authored there", () => {
    expect(planExperimentRunScriptSeed({ ...base, targetExists: true })).toBeNull();
  });

  // The path is derived from the name, so an unnamed experiment has no
  // destination — and the backend could not declare it either way.
  it("does not seed for an experiment that has no name yet", () => {
    expect(planExperimentRunScriptSeed({ ...base, name: "   " })).toBeNull();
  });

  it("carries the authored script over when a rename moved its destination", () => {
    expect(
      planExperimentRunScriptSeed({
        ...base,
        name: "renamed",
        declaredPath: "ree-scripts/experiments/python-hello.sh",
        declaredContent: "#!/usr/bin/env sh\necho authored\n",
        targetPath: "ree-scripts/experiments/renamed.sh",
      }),
    ).toEqual({
      fromPath: "ree-scripts/experiments/python-hello.sh",
      toPath: "ree-scripts/experiments/renamed.sh",
      content: "#!/usr/bin/env sh\necho authored\n",
    });
  });

  // A declaration pointing at a file that is gone leaves nothing to carry, so
  // the rename seeds the template rather than moving a file that isn't there.
  it("falls back to the template when the declared script is missing", () => {
    expect(
      planExperimentRunScriptSeed({
        ...base,
        name: "renamed",
        declaredPath: "ree-scripts/experiments/python-hello.sh",
        declaredContent: null,
        targetPath: "ree-scripts/experiments/renamed.sh",
      }),
    ).toEqual({
      toPath: "ree-scripts/experiments/renamed.sh",
      content: "#!/usr/bin/env sh\n",
    });
  });
});
