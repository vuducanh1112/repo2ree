"""Runtime execution mechanics: subprocesses, runnables, external tools.

    process             the generic cancellable subprocess runner
    experiment/spec     projecting a portable definition into an executable plan
    experiment/run      executing it and capturing what it produced
    tools               locating the external binaries a run needs

Handlers coordinate execution; execution never reaches back into them.
Runnable definitions live in the portable REE domain; execution consumes only
their minimal script-and-output projection.
"""
