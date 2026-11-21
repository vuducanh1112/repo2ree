"""Exercises drawn at random, for Hypothesis to search and shrink.

An exercise drawn uniformly dies at its first step: an REE no step made, a seal before a source. So each REE follows
a pipeline as an author or a reviewer would, one stage at a time, and some steps leave it: any operation, with any of
a few inputs, wherever the REE stands. A stage is taken whether or not its step would succeed, which is the
specification's to judge from the trace, never the generator's to know.

Inputs come from small fixed pools (the instant project, its recipe, one experiment), so a failing exercise shrinks
to steps that differ in what matters. Drifts name a part of an REE and a change, and replay picks the file.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, assert_never, get_args

from hypothesis import strategies as st

from repo2ree_testbed.api_models import (
    DefinitionPatch,
    ExperimentEnvironmentPatch,
    ExperimentPatch,
    ReviewBasis,
    ScriptKind,
    ScriptTarget,
)
from repo2ree_testbed.exercise import (
    AcquireSource,
    ActivateExperimentEnvironment,
    BuildExperimentEnvironment,
    CheckWorkingEnvironment,
    CrossCheckSbom,
    Drift,
    EvaluateReproducibility,
    Exercise,
    FileChange,
    FileDrift,
    FilePart,
    FromRecipe,
    GenerateSbom,
    HistoryChange,
    HistoryDrift,
    InitializeRee,
    Label,
    LintScripts,
    LoadReeBundle,
    MaterializeWorkspace,
    ObserveHardware,
    PatchReeDefinition,
    ReflogDrift,
    RemoveSource,
    RevertedDrift,
    ReviewAcquireSource,
    ReviewActivateExperimentEnvironment,
    ReviewBuildExperimentEnvironment,
    ReviewRunExperiment,
    ReviewSignature,
    RunExperiment,
    SealRee,
    SealSignature,
    SignRee,
    SignReview,
    StampsDrift,
    Step,
    SuggestScripts,
    Text,
    Uploaded,
    WriteScript,
)
from repo2ree_testbed.showcases import INSTANT, RESULT, RecipeScript

AUTHOR: Final = "author"
REVIEWER: Final = "reviewer"
REVIEWS: Final[tuple[Label, ...]] = ("first", "second")
EXPERIMENT: Final = INSTANT.experiment
UNDECLARED: Final = "undeclared"
TEXTS: Final = ("exit 0\n", "exit 1\n")
PER_EXPERIMENT: Final = frozenset({"experiment_run", "experiment_verify"})
# Of every ten steps, how many follow the pipeline.
FOLLOWED: Final = 8

type Stage = Callable[[Label], Step]


def recipe_file(script: ScriptKind) -> RecipeScript | None:
    """The file of a project's recipe that writes ``script``; None for one no recipe writes."""
    match script:
        case "check_working_environment":
            return "check_working_environment.sh"
        case "build_experiment_environment":
            return "build_experiment_environment.sh"
        case "activate_experiment_environment":
            return "activate_experiment_environment.sh"
        case "experiment_run":
            return "experiment.sh"
        case "experiment_verify":
            return "experiment.verify.sh"
        case "launch":
            return None
    assert_never(script)


def _from_recipe(script: ScriptKind) -> FromRecipe:
    file = recipe_file(script)
    if file is None:
        raise ValueError(f"no recipe writes {script}")
    return FromRecipe(project=INSTANT.name, file=file)


def _recipe(script: ScriptKind) -> Stage:
    experiment = EXPERIMENT if script in PER_EXPERIMENT else None
    content = _from_recipe(script)
    return lambda ree: WriteScript(ree=ree, script=script, experiment=experiment, content=content)


DECLARE_ENVIRONMENT: Final = DefinitionPatch(
    experiment_environment=ExperimentEnvironmentPatch(artifact_path=INSTANT.experiment_environment_path)
)
DECLARE_EXPERIMENT: Final = DefinitionPatch(experiments=(ExperimentPatch(name=EXPERIMENT, output_paths=(RESULT,)),))

REVIEW: Final[tuple[Stage, ...]] = (
    lambda ree: ReviewAcquireSource(ree=ree, review=REVIEWS[0]),
    lambda ree: ReviewBuildExperimentEnvironment(ree=ree, review=REVIEWS[0]),
    lambda ree: ReviewActivateExperimentEnvironment(ree=ree, review=REVIEWS[0]),
    lambda ree: ReviewRunExperiment(ree=ree, review=REVIEWS[0], experiment=EXPERIMENT),
    lambda ree: SignReview(ree=ree, review=REVIEWS[0]),
)
AUTHORING: Final[tuple[Stage, ...]] = (
    lambda ree: InitializeRee(ree=ree),
    lambda ree: AcquireSource(ree=ree, source=Uploaded(project=INSTANT.name)),
    _recipe("check_working_environment"),
    lambda ree: CheckWorkingEnvironment(ree=ree),
    lambda ree: PatchReeDefinition(ree=ree, patch=DECLARE_ENVIRONMENT),
    _recipe("build_experiment_environment"),
    _recipe("activate_experiment_environment"),
    lambda ree: BuildExperimentEnvironment(ree=ree),
    lambda ree: ActivateExperimentEnvironment(ree=ree),
    lambda ree: PatchReeDefinition(ree=ree, patch=DECLARE_EXPERIMENT),
    _recipe("experiment_run"),
    _recipe("experiment_verify"),
    lambda ree: RunExperiment(ree=ree, experiment=EXPERIMENT),
    lambda ree: SealRee(ree=ree),
    lambda ree: SignRee(ree=ree),
)
# A lone REE reviews its own seal; a reviewer loads the author's.
ALONE: Final = (*AUTHORING, *REVIEW)
REVIEWING: Final[tuple[Stage, ...]] = (
    lambda ree: InitializeRee(ree=ree),
    lambda ree: LoadReeBundle(ree=ree, exported_by=AUTHOR),
    *REVIEW,
)

TARGETS: Final = st.lists(
    st.sampled_from(
        [
            ScriptTarget(kind=kind, experiment_name=EXPERIMENT if kind in PER_EXPERIMENT else None)
            for kind in get_args(ScriptKind)
        ]
    ),
    min_size=1,
    max_size=2,
    unique=True,
).map(tuple)


def _script(ree: Label) -> st.SearchStrategy[Step]:
    @st.composite
    def drawn(draw: st.DrawFn) -> Step:
        script: ScriptKind = draw(st.sampled_from(get_args(ScriptKind)))
        experiment = draw(st.sampled_from((EXPERIMENT, UNDECLARED))) if script in PER_EXPERIMENT else None
        texts = st.sampled_from(TEXTS).map(lambda text: Text(text=text))
        recipe = st.just(_from_recipe(script)) if recipe_file(script) else st.nothing()
        return WriteScript(ree=ree, script=script, experiment=experiment, content=draw(recipe | texts))

    return drawn()


def _patch(ree: Label) -> st.SearchStrategy[Step]:
    patches = st.sampled_from(
        (
            DECLARE_ENVIRONMENT,
            DECLARE_EXPERIMENT,
            DefinitionPatch(name="renamed"),
            DefinitionPatch(experiments=()),
            DefinitionPatch(experiments=(ExperimentPatch(name=UNDECLARED, output_paths=(RESULT,)),)),
        )
    )
    return patches.map(lambda patch: PatchReeDefinition(ree=ree, patch=patch))


def _deviation(ree: Label, others: tuple[Label, ...]) -> st.SearchStrategy[Step]:
    """Any operation in ``ree``, with any of a few inputs, wherever it stands."""
    reviews = st.sampled_from(REVIEWS)
    bases = st.sampled_from(get_args(ReviewBasis))
    experiments = st.sampled_from((EXPERIMENT, UNDECLARED))
    operations: list[st.SearchStrategy[Step]] = [
        st.just(InitializeRee(ree=ree)),
        st.just(AcquireSource(ree=ree, source=Uploaded(project=INSTANT.name))),
        st.just(RemoveSource(ree=ree)),
        _patch(ree),
        _script(ree),
        TARGETS.map(lambda targets: SuggestScripts(ree=ree, targets=targets)),
        TARGETS.map(lambda targets: LintScripts(ree=ree, targets=targets)),
        st.booleans().map(lambda strict: EvaluateReproducibility(ree=ree, strict=strict)),
        st.just(ObserveHardware(ree=ree)),
        st.just(CheckWorkingEnvironment(ree=ree)),
        st.just(MaterializeWorkspace(ree=ree)),
        st.just(BuildExperimentEnvironment(ree=ree)),
        st.just(GenerateSbom(ree=ree)),
        st.just(CrossCheckSbom(ree=ree)),
        st.just(ActivateExperimentEnvironment(ree=ree)),
        experiments.map(lambda experiment: RunExperiment(ree=ree, experiment=experiment)),
        st.builds(
            SealRee,
            ree=st.just(ree),
            source_included=st.booleans(),
            experiment_environment_included=st.booleans(),
            results_included=st.booleans(),
        ),
        st.sampled_from(get_args(SealSignature)).map(lambda signature: SignRee(ree=ree, signature=signature)),
        st.builds(ReviewAcquireSource, ree=st.just(ree), review=reviews, basis=bases),
        st.builds(ReviewBuildExperimentEnvironment, ree=st.just(ree), review=reviews, basis=bases),
        st.builds(ReviewActivateExperimentEnvironment, ree=st.just(ree), review=reviews),
        st.builds(ReviewRunExperiment, ree=st.just(ree), review=reviews, experiment=experiments),
        st.builds(SignReview, ree=st.just(ree), review=reviews, signature=st.sampled_from(get_args(ReviewSignature))),
    ]
    if others:
        operations.append(st.sampled_from(others).map(lambda other: LoadReeBundle(ree=ree, exported_by=other)))
    return st.one_of(operations)


def _drifts(steps: tuple[Step, ...]) -> st.SearchStrategy[tuple[Drift, ...]]:
    """Drifts in REEs the steps initialize, each after the step that does: of any part, by any change, kept or put back
    by hand, a history changed by git, or ree's stamps or git's reflog lost, in the REE or in a review the steps
    name."""
    initialized = {
        step.ree: index for index, step in reversed(list(enumerate(steps))) if isinstance(step, InitializeRee)
    }
    if not initialized:
        return st.just(())
    reviewed = sorted({review for step in steps if (review := getattr(step, "review", None)) is not None})

    def one(ree: Label) -> st.SearchStrategy[Drift]:
        first = initialized[ree] + 1
        reviews: st.SearchStrategy[Label | None] = st.none() | st.sampled_from(reviewed) if reviewed else st.none()
        before = st.integers(min_value=first, max_value=len(steps))

        def changed(kind: type[FileDrift | RevertedDrift]) -> st.SearchStrategy[Drift]:
            return st.sampled_from(get_args(FilePart)).flatmap(
                lambda part: st.builds(
                    kind,
                    before=before,
                    ree=st.just(ree),
                    review=reviews,
                    part=st.just(part),
                    # Nothing added beside the records is the REE's.
                    change=st.sampled_from(
                        [change for change in get_args(FileChange) if (part, change) != ("records", "add")]
                    ),
                    pick=st.integers(min_value=0, max_value=50),
                )
            )

        lost = st.sampled_from([StampsDrift, ReflogDrift]).flatmap(
            lambda kind: st.builds(kind, before=before, ree=st.just(ree), review=reviews)
        )
        files = st.one_of(changed(FileDrift), changed(RevertedDrift), lost)
        if first >= len(steps):
            return files
        history: st.SearchStrategy[Drift] = st.integers(min_value=first, max_value=len(steps) - 1).flatmap(
            lambda before: st.builds(
                HistoryDrift,
                before=st.just(before),
                ree=st.just(ree),
                review=reviews,
                change=st.sampled_from(get_args(HistoryChange)),
                until=st.integers(min_value=before + 1, max_value=len(steps)),
            )
        )
        return st.one_of(files, history)

    return st.lists(st.sampled_from(sorted(initialized)).flatmap(one), max_size=2).map(tuple)


@st.composite
def exercises(draw: st.DrawFn, max_steps: int = 30) -> Exercise:
    """An exercise of one REE that authors and reviews itself, or of an author and a reviewer of its seal."""
    rees: tuple[Label, ...] = draw(st.sampled_from(((AUTHOR,), (AUTHOR, REVIEWER))))
    pipelines = {AUTHOR: ALONE if len(rees) == 1 else AUTHORING, REVIEWER: REVIEWING}
    stage = dict.fromkeys(rees, 0)
    steps: list[Step] = []
    for _ in range(draw(st.integers(min_value=1, max_value=max_steps))):
        ree = draw(st.sampled_from(rees))
        pipeline = pipelines[ree]
        if stage[ree] < len(pipeline) and draw(st.integers(min_value=0, max_value=9)) < FOLLOWED:
            steps.append(pipeline[stage[ree]](ree))
            stage[ree] += 1
        else:
            steps.append(draw(_deviation(ree, tuple(other for other in rees if other != ree))))
    return Exercise(rees=rees, steps=tuple(steps), drifts=draw(_drifts(tuple(steps))))
