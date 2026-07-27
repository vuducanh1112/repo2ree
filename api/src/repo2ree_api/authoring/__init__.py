"""The author's side of the REE step graph.

The modules here follow ``repo2ree_core.evidence.steps.REE_STEPS`` — the step list
this API publishes through ``listReeSteps``. Steps that advance by running
something in the workbench are together in :mod:`stages`; the ones that advance
by declaring (source, metadata, seal) have their own module, and :mod:`catalog`
carries the join table from step key to the operationIds that advance it.

The reviewer traverses the same lifecycle over in :mod:`repo2ree_api.review`.
"""
