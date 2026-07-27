"""Runtime execution mechanics: subprocesses, runnables, external tools.

    process             the generic cancellable subprocess runner
    experiment/resolve  turning a declared runnable into an executable one
    experiment/run      executing it and capturing what it produced
    tools               locating the external binaries a run needs

Handlers coordinate execution; execution never reaches back into them.
The models a runnable is *declared* with live in ``domain.experiment`` — what a
runnable is outlives any particular way of running it.
"""
