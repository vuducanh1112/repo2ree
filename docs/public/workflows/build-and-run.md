# Build and Run an REE

Build and run is the author-side loop: take source, add the instructions needed
to execute it, build a runtime, and run declared commands inside that runtime.

## Current flow

1. Create an REE workspace.
2. Acquire source from a URL or upload.
3. Add metadata and build/runtime instructions.
4. Run Evaluate to inspect reproducibility evidence.
5. Build the runtime.
6. Generate SBOM and HBOM evidence.
7. Test activation.
8. Run declared experiment commands.

The current prototype executes work in an isolated Docker-backed workbench. The
API sends typed commands into that workbench and streams logs and results back
to the frontend.

## Runtime evidence

A useful REE needs more than "it ran once." repo2ree collects evidence around
the run:

- build logs and status;
- the selected runtime artifact;
- SBOM records for software contents;
- HBOM records for hardware context;
- activation status;
- experiment outputs and declared output checks.

## Experiment runs

Experiment commands can be run from the app and checked against declared output
expectations. This is the foundation for Run Receipts, but the current public
object is still an execution result rather than a fully citable receipt.

The target receipt will make each run durable: command, inputs, outputs, traces,
comparison policy, predecessor lineage, and signatures.
