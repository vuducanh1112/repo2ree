# How to build and run an REE

Build and run is the author-side loop: take source, add the instructions needed
to execute it, build a runtime, and run declared commands inside that runtime.

## Current flow

1. Create an REE workspace.
2. Acquire source from a URL or upload.
3. Add metadata and build/runtime instructions.
4. Run Evaluate to assess source declarations and reproducibility risks.
5. Build the runtime.
6. Generate SBOM and HBOM evidence.
7. Test activation.
8. Run declared experiment commands.

The current prototype executes work in an isolated Docker-backed workbench. The
API sends typed commands into that workbench and streams logs and results back
to the GUI.

## Runtime evidence

A useful REE needs more than "it ran once." repo2ree collects evidence around
the run:

- build logs and status;
- the selected runtime artifact;
- SBOM records for software contents;
- HBOM records for hardware context;
- activation status;
- experiment run evidence and the verify-script verdict.

## Experiment runs

The app runs each experiment command and then applies an author-provided verify
script. Both scripts run from the workspace root with no injected environment.
The verify script inspects workspace files, and its exit code is the verdict.
To check stdout, the run script must first write it to a workspace file.

When both scripts pass, the run is **validated** against the declared check. It
is not a reproduction: that requires a later run compared with author evidence.
The operation stores an immutable typed receipt in the REE. Independently
citable receipts with predecessor lineage, signatures, and deposit formats
remain target work.

A successful run captures its declared output files in a per-experiment results
store and records their digest in the receipt. An experiment can include those
results in the sealed bundle as the author baseline for later comparison (see
[Verify](verify.md)).

The target receipt will make each run durable: command, inputs, outputs, traces,
verification policy, predecessor lineage, and signatures.
