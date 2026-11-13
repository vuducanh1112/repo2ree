"""The launch-inference decision DAG.

A fork into one branch per launcher, joined by the score-free resolver; Slurm is the only launcher for now. A
launch is proposed only where its launcher answers, and always for confirmation: what each script needs from
the cluster (CPUs, memory, time, GPUs) is the author's to say, and nothing in the source says it. Where no
launcher answers, nothing is inferred, and the REE runs its scripts directly, with no launch script at all.
"""

from __future__ import annotations

from repo2ree_protocol.inference import CheckNode, DecisionDag, ForkNode, ResolveNode, ResultNode, StrategyLeafNode

SLURM_LAUNCH_RULE = "slurm-job-step-launch"

LAUNCH_DAG = DecisionDag(
    key="launch-inference",
    version=1,
    root="launchers",
    nodes=[
        ForkNode(id="launchers", branches={"slurm": "slurm"}, join="resolve-launchers"),
        CheckNode(
            id="slurm",
            check="slurm",
            branches={"usable": "slurm-launch", "unknown": "slurm-unprobed", "unavailable": "slurm-not-applicable"},
        ),
        StrategyLeafNode(
            id="slurm-launch",
            strategy="slurm",
            outcome="candidate",
            rule=SLURM_LAUNCH_RULE,
            warnings=["launch_needs_unset"],
            render="slurm_launch",
            next="resolve-launchers",
        ),
        StrategyLeafNode(
            id="slurm-unprobed",
            strategy="slurm",
            outcome="candidate",
            rule=SLURM_LAUNCH_RULE,
            warnings=["launch_needs_unset"],
            render="slurm_launch",
            next="resolve-launchers",
        ),
        StrategyLeafNode(
            id="slurm-not-applicable",
            strategy="slurm",
            outcome="not_applicable",
            next="resolve-launchers",
        ),
        ResolveNode(
            id="resolve-launchers",
            fork="launchers",
            resolver="score_free_viability_v1",
            branches={
                "complete": "launch-complete",
                "needs_input": "launch-needs-input",
                "not_inferred": "launch-not-inferred",
            },
        ),
        ResultNode(id="launch-complete", status="complete", application="automatic_allowed"),
        ResultNode(id="launch-needs-input", status="needs_input", application="confirmation_required"),
        ResultNode(id="launch-not-inferred", status="not_inferred", application="unavailable"),
    ],
)
