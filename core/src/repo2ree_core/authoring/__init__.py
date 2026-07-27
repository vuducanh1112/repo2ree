"""Code that derives or generates the material an REE is authored out of.

    script_inference   reading a repository and proposing candidate scripts
    script_generation  emitting the infrastructure scripts baked into an REE

The distinction the old ``ree_scripts`` name lost: these are Python modules
that *generate* scripts, not the scripts themselves. The reserved paths those
scripts land on, and their starter templates, stay at the package root — they
are leaves that ``domain`` and ``ree`` both depend on.
"""
