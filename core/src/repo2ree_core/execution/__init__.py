"""Runtime execution mechanics: subprocesses and runnables.

    process             the generic cancellable subprocess runner
    experiment/spec     projecting a portable definition into an executable plan
    experiment/run      executing it and capturing what it produced

External-tool lookup lives in the shared leaf module ``repo2ree_core.tooling``.

Handlers coordinate execution; execution never reaches back into them.
Runnable definitions live in the portable REE domain; execution consumes only
their minimal script-and-output projection.
"""
