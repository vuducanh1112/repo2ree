"""What makes a bundle run without repo2ree — and the verbs it runs by.

Reproducing an REE means acquiring its source, assembling a clean workspace,
building the runtime, testing activation, and running the experiments. The
workbench does that by dispatching commands; a stranger who downloaded a bundle
does it by running ``sh run.sh``. Both must mean the same thing by every step,
or a bundle stops being evidence of anything.

That is what this package is for. ``commands`` holds the verb vocabulary the
executor CLI and the generated ``run.sh`` both expose, so their ``--help``
cannot drift. The rest generate the portable POSIX shell that implements it:

    acquire_source        the shared acquire muscle — snapshot, else origin
    materialize_workspace the shared merge muscle — upstream + overlay
    reproducer            run.sh and REPRODUCING.md, the bundle's front door
    shell                 quoting and placeholder checks the three share

These are Python modules that *generate* scripts, not the scripts themselves —
the REE's own machinery, which an author never edits. What an author does edit
is proposed by ``author_recipes``.
"""
