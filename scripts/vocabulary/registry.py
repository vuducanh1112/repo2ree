"""The repository's vocabulary graph. This file is protected (zones.toml, gates): a relation changes apart from
the names it holds, so it cannot be loosened beside the code it would fail."""

from __future__ import annotations

from scripts.vocabulary.model import Edge, Graph, Ignored, Origin, Relation, Vocabulary
from scripts.vocabulary.readers import (
    CatalogueTable,
    CommandsRunByName,
    ContractSet,
    GuiVocabularySet,
    OperationsNamed,
    RoutedOperations,
    SourceSet,
    SourceSites,
    SpecFieldGroups,
    SpecReceipts,
)

EQUALS, WITHIN, DERIVED = Relation.EQUALS, Relation.WITHIN, Relation.DERIVED
SPEC, CONTRACT, SOURCE = Origin.SPEC, Origin.CONTRACT, Origin.SOURCE

OPERATIONS = ("operations", "review_operations")
# The author API's actions that run no operation: reads, and the REE's own creation, deletion and upload.
API_ACTIONS = (
    "create_ree",
    "delete_ree",
    "download_ree",
    "list_actions",
    "list_receipts",
    "read_file",
    "upload_source",
    "view_action",
    "view_action_log",
    "view_history",
    "view_ree",
    "view_ree_state",
    "view_reproducibility_report",
    "watch_action",
)
# The REE definition's fields that are no stage's: what the REE is, and the parts its stages declare.
DEFINITION_FIELDS = ("catalog", "experiment_environment", "experiments", "hbom", "launch", "name", "source")


def _source(name: str, site: str, summary: str) -> Vocabulary:
    return Vocabulary(name, SOURCE, SourceSet(site), summary)


def _contract(name: str, summary: str, *patterns: str) -> Vocabulary:
    return Vocabulary(name, CONTRACT, ContractSet(patterns), summary)


def _gui(name: str, constant: str, summary: str) -> Vocabulary:
    return Vocabulary(name, CONTRACT, GuiVocabularySet(constant), summary)


VOCABULARIES = (
    # ---- the roots ----
    Vocabulary("operations", SPEC, CatalogueTable("operations"), "Every operation core runs on an REE."),
    Vocabulary("review_operations", SPEC, CatalogueTable("review_operations"), "Every operation on a review."),
    # ---- the specification ----
    Vocabulary("spec.receipts", SPEC, SpecReceipts(), "The Ree aggregate's receipts."),
    Vocabulary("spec.groups", SPEC, SpecFieldGroups(), "The groups the aggregate's fields are drawn in."),
    _contract(
        "behaviour.receipt_kinds",
        "A Receipt fact's kind, published from the specification.",
        "behaviour:/$defs/Receipt/*/facts/properties/kind/enum",
    ),
    _contract(
        "behaviour.operations",
        "An Attempt's, an Execution's and a start_run's operation, published from the catalogue.",
        "behaviour:/$defs/Attempt/*operation/enum",
        "behaviour:/$defs/Execution/*operation/enum",
        "behaviour:/$defs/start_run/*operation/enum",
    ),
    _contract(
        "behaviour.author_api_actions",
        "An AuthorApiAction fact's action.",
        "behaviour:/$defs/AuthorApiAction/*/facts/properties/action/enum",
    ),
    # ---- what the contracts name ----
    Vocabulary("contracts.operation_names", CONTRACT, OperationsNamed(), "Every operation a contract names."),
    Vocabulary("cli.commands", CONTRACT, CommandsRunByName(), "The operations a `ree` command spelled as each runs."),
    Vocabulary("http.declared", CONTRACT, RoutedOperations("declared"), "The operations a route starts."),
    Vocabulary("http.named", CONTRACT, RoutedOperations("named"), "The operations a route is named after."),
    Vocabulary(
        "http.posted", CONTRACT, RoutedOperations("posted"), "The operations whose named route is placed right."
    ),
    _contract(
        "run.operations", "A run's operation.", "openapi:/components/schemas/RunSummary/properties/operation/enum"
    ),
    # ---- the stages ----
    _contract(
        "ree.receipts",
        "The REE's receipts: one slot per stage that files one.",
        "*:/$defs/ReeReceipts/properties",
        "openapi:/components/schemas/ReeReceipts/properties",
    ),
    _contract(
        "ree.audit",
        "What the audit reports on: one step audit per receipt.",
        "*:/$defs/ReeAudit/properties",
        "openapi:/components/schemas/ReeAudit/properties",
    ),
    _contract(
        "steps",
        "The steps of authoring an REE, as `ree status` and the API's step catalogue name them.",
        "*:/$defs/ReeStepState/properties/key/enum",
        "*:/$defs/ReeStepState/properties/requires/items/enum",
        "*:/$defs/ReeSteps/properties/next/anyOf/0/enum",
        "openapi:/components/schemas/ReeStep*/properties/key/enum",
        "openapi:/components/schemas/ReeStep*/properties/requires/items/enum",
        "openapi:/components/schemas/ReeStep*/properties/next/anyOf/0/enum",
    ),
    _contract(
        "review.steps",
        "The steps of a review attempt.",
        "*:/$defs/ReviewStepState/properties/step/enum",
        "openapi:/components/schemas/ReviewStepState/properties/step/enum",
    ),
    _contract(
        "review.receipts",
        "A review attempt's receipts.",
        "*:/$defs/ReviewReceipts/properties",
        "openapi:/components/schemas/ReviewReceipts/properties",
    ),
    _contract(
        "ree.definition",
        "The REE definition's fields: its declarations, some named for the stage that runs them.",
        "*:/$defs/ReeDefinition/properties",
        "openapi:/components/schemas/ReeDefinition-*/properties",
    ),
    _contract(
        "script.kinds",
        "The kinds of script an REE has: a stage's, the launch, an experiment's run and verify.",
        "*:/$defs/ScriptTarget/properties/kind/enum",
        "*:/$defs/ScriptTargetSelectorArg/properties/kind/enum",
        "*:/$defs/LintDraftQuery/properties/kind/enum",
        "*:/$defs/ScriptState/properties/kind/enum",
        "openapi:/components/schemas/ScriptTarget*/properties/kind/enum",
    ),
    _contract(
        "script.templates",
        "The script template catalogue: each kind's templates and where its scripts belong.",
        "*:/*ScriptTemplateCatalog/properties",
    ),
    # ---- the GUI's vocabulary, generated from the OpenAPI contract ----
    _gui("gui.steps", "STEP_KEYS", "The steps of authoring an REE, as the GUI reads them."),
    _gui("gui.review_steps", "REVIEW_STEP_KEYS", "The steps of a review attempt, as the GUI reads them."),
    _gui("gui.run_operations", "REE_RUN_OPERATIONS", "A run's operation, as the GUI reads it."),
    _gui("gui.audit", "REE_AUDIT_KEYS", "What the audit reports on, as the GUI reads it."),
    _gui("gui.receipts", "REE_RECEIPT_KEYS", "The REE's receipt slots, as the GUI reads them."),
    _gui("gui.receipt_operations", "RECEIPT_OPERATIONS", "The operations that file the REE's receipts."),
    _gui("gui.script_kinds", "SCRIPT_KINDS", "The kinds of script an REE has, as the GUI reads them."),
    Vocabulary(
        "gui.lint_names",
        SOURCE,
        SourceSites("gui/biome.json::match.*", "copies"),
        "The wire names Biome lets a property be spelled as, generated with the GUI's vocabulary.",
    ),
    # ---- source: the literals the contracts render from ----
    _source(
        "protocol.operation_name", "protocol/src/repo2ree_protocol/command.py::OperationName", "A command's operation."
    ),
    _source("protocol.step_key", "protocol/src/repo2ree_protocol/catalog.py::ReeStepKey", "The step keys."),
    _source("protocol.target_kind", "protocol/src/repo2ree_protocol/command.py::TargetKind", "The script kinds."),
    _source("ree.review_step_key", "ree/src/repo2ree_ree/review.py::ReviewStepKey", "The review's step keys."),
    _source(
        "telemetry.author_api_action",
        "telemetry/src/repo2ree_telemetry/behaviour/events.py::AuthorApiActionName",
        "The author API's actions, as the telemetry records them.",
    ),
    # ---- source: hand-written copies, held here and nowhere else ----
    _source(
        "protocol.outputs", "protocol/src/repo2ree_protocol/outputs.py::OUTPUTS", "Each operation's outputs model."
    ),
    _source("core.step_complete", "core/src/repo2ree_core/domain/ree/steps.py::_COMPLETE", "When each step is done."),
    _source("cli.step_hints", "cli/src/repo2ree_cli/render.py::HINTS", "What `ree status` says to run for each step."),
    _source(
        "api.step_actions", "api/src/repo2ree_api/authoring/catalog.py::_STEP_ACTIONS", "The routes advancing a step."
    ),
    _source(
        "core.step_evidence",
        "core/src/repo2ree_core/operations/capture.py::step_evidence.standing",
        "The receipts whose standing a capture records.",
    ),
    _source(
        "traceview.step_order",
        "assurance/traceview/src/repo2ree_assurance_traceview/terms.py::STEP_ORDER",
        "The order traceview draws receipts in.",
    ),
    _source("cli.review_all", "cli/src/repo2ree_cli/cli.py::review_all.operations", "What `ree review all` runs."),
    _source(
        "core.runnable_kind",
        "core/src/repo2ree_core/operations/handlers/author/runnable.py::RunnableKind",
        "The operations that run a script inside the experiment environment.",
    ),
    _source(
        "core.sealed_by",
        "core/src/repo2ree_core/bundle/download.py::SEALED_BY",
        "The operations whose commit is a sealed REE as it is exported: the seal and each signature.",
    ),
    _source(
        "core.fixed_scripts",
        "core/src/repo2ree_core/operations/handlers/author/definition_authoring.py::FIXED_SCRIPTS",
        "The definition's declarations of the scripts every REE has.",
    ),
    _source(
        "authoring.fixed_targets",
        "authoring/src/repo2ree_authoring/targets.py::resolve_target.path",
        "Where each fixed script is.",
    ),
    _source(
        "core.fixed_targets",
        "core/src/repo2ree_core/operations/read_models/ree_document.py::_script_targets.fixed",
        "The fixed scripts the REE document lists.",
    ),
    _source(
        "core.inference_dags",
        "core/src/repo2ree_core/author_recipes/inference/registry.py::DAG_FOR_TARGET_KIND",
        "The script kinds inference proposes for.",
    ),
    _source(
        "authoring.lint.exit_status",
        "authoring/src/repo2ree_authoring/lint/rules/exit_status.py::PipeMaskingRule.applies_to",
        "The kinds a lint rule reads.",
    ),
    _source(
        "authoring.lint.experiment_environment_reference",
        "authoring/src/repo2ree_authoring/lint/rules/experiment_environment_reference.py"
        "::ExperimentEnvironmentReferenceRule.applies_to",
        "The kinds a lint rule reads.",
    ),
    _source(
        "authoring.lint.placeholders",
        "authoring/src/repo2ree_authoring/lint/rules/placeholders.py::UneditedPlaceholderRule.applies_to",
        "The kinds a lint rule reads.",
    ),
    _source(
        "testbed.script_kind", "testbed/src/repo2ree_testbed/api_models.py::ScriptKind", "The testbed's script kinds."
    ),
    # ---- the GUI's hand-chosen sets, each typed by its generated vocabulary ----
    _source(
        "gui.dock_steps",
        "gui/src/core/ree-steps/ReeStepParams.ts::REE_STEP_KEYS",
        "The steps a page runs from its dock.",
    ),
    _source(
        "gui.dock_step_defaults",
        "gui/src/core/ree-steps/stepCatalog.ts::DEFAULT_REE_STEP_PARAMS",
        "Each dock step's default parameters.",
    ),
    *(
        _source(f"gui.dock_steps.{name}", f"gui/src/core/ree-steps/{site}", "Keyed by the dock steps.")
        for name, site in (
            ("params", "ReeStepParams.ts::ReeStepParamsByKey"),
            ("run_params", "stepRunParams.ts::ReeStepRunParamsByKey"),
            ("run_requests", "stepRunRequests.ts::ReeStepRunRequestByKey"),
            ("requirements", "stepPolicies.ts::REE_STEP_REQUIREMENTS"),
            ("planners", "stepCommands.ts::createStepCommandPlanners"),
        )
    ),
    _source(
        "gui.step_pages",
        "gui/src/core/app-shell/authoringDag.ts::PAGE_BY_STEP",
        "The page each step the GUI shows is done on.",
    ),
    _source(
        "gui.fixed_declarations",
        "gui/src/shell/data/ree/fixedDeclarations.ts::fixedDeclarations",
        "The definition fields that declare an REE's fixed scripts.",
    ),
    _source(
        "gui.workspace_refresh_steps",
        "gui/src/core/ree-steps/stepPolicies.ts::WORKSPACE_REFRESH_STEPS",
        "The dock steps after which the workspace is read again.",
    ),
    _source(
        "gui.page_receipts",
        "gui/src/core/canvas/canvasNodes.ts::RECEIPT_OPERATIONS_BY_PAGE",
        "The receipts each canvas page shows.",
    ),
    _source(
        "gui.receipt_labels",
        "gui/src/core/receipts/authorReceipts.ts::OPERATION_LABELS",
        "The receipts console's title for each receipt.",
    ),
    Vocabulary(
        "gui.run_hud_tabs",
        SOURCE,
        SourceSites("gui/src/core/runs/runHud.ts::RUN_HUD_TABS*", "union"),
        "The run operations the logs HUD's tabs hold.",
    ),
    _source(
        "gui.review_subjects",
        "gui/src/shell/ui/app-shell/canvas/review/ReviewStrip.tsx::STEP_SUBJECT",
        "What each review step compares.",
    ),
    _source(
        "gui.inference_kinds",
        "gui/src/shell/data/scriptInference/candidate.ts::SCRIPT_TARGET_KINDS",
        "The scripts a page infers.",
    ),
    _source(
        "gui.lint_kinds",
        "gui/src/shell/data/scriptLint/findings.ts::LINT_TARGET_KINDS",
        "The scripts a page lints.",
    ),
)

EDGES = (
    # ---- operations, as the interfaces spell them ----
    Edge("contracts.operation_names", WITHIN, OPERATIONS),
    Edge("cli.commands", EQUALS, OPERATIONS),
    Edge("http.declared", WITHIN, OPERATIONS),
    Edge("http.named", EQUALS, ("http.declared",)),
    Edge("http.posted", EQUALS, ("http.named",)),
    Edge("protocol.operation_name", EQUALS, OPERATIONS),
    Edge("run.operations", DERIVED, ("protocol.operation_name",)),
    Edge("behaviour.operations", DERIVED, OPERATIONS),
    Edge("behaviour.author_api_actions", WITHIN, ("operations",), API_ACTIONS),
    # ---- the stages ----
    Edge("ree.receipts", WITHIN, ("operations",), ("experiments",)),
    Edge("ree.audit", EQUALS, ("ree.receipts",)),
    Edge("protocol.step_key", WITHIN, ("operations",), ("experiments", "metadata")),
    Edge("steps", DERIVED, ("protocol.step_key",)),
    Edge("ree.receipts", WITHIN, ("steps",)),
    Edge("ree.review_step_key", WITHIN, ("operations",), ("experiments",)),
    Edge("review.steps", DERIVED, ("ree.review_step_key",)),
    Edge("review.receipts", EQUALS, ("review.steps",)),
    # A receipt is named after the operation producing it; the REE keeps the experiments' together.
    Edge("spec.receipts", WITHIN, ("operations",)),
    Edge("spec.receipts", WITHIN, ("ree.receipts",), ("run_experiment",)),
    Edge("ree.receipts", WITHIN, ("spec.receipts",), ("experiments",)),
    Edge("behaviour.receipt_kinds", DERIVED, ("spec.receipts",)),
    Edge("spec.groups", WITHIN, ("spec.receipts",), ("bundle", "catalog", "launch")),
    Edge("ree.definition", WITHIN, ("operations",), DEFINITION_FIELDS),
    Edge("protocol.target_kind", WITHIN, ("operations",), ("experiment_run", "experiment_verify", "launch")),
    Edge("script.kinds", DERIVED, ("protocol.target_kind",)),
    Edge("script.templates", EQUALS, ("script.kinds",)),
    Edge("telemetry.author_api_action", EQUALS, ("behaviour.author_api_actions",)),
    # ---- hand-written copies ----
    Edge("protocol.outputs", WITHIN, OPERATIONS),
    Edge("core.step_complete", EQUALS, ("steps",)),
    Edge("cli.step_hints", EQUALS, ("steps",)),
    Edge("api.step_actions", EQUALS, ("steps",)),
    Edge("core.step_evidence", WITHIN, ("ree.receipts",)),
    Edge("traceview.step_order", WITHIN, ("spec.receipts",)),
    Edge("cli.review_all", EQUALS, ("review_operations",)),
    Edge("core.runnable_kind", WITHIN, ("operations",)),
    Edge("core.sealed_by", WITHIN, ("operations",)),
    Edge("core.fixed_scripts", WITHIN, ("ree.definition",)),
    Edge("authoring.fixed_targets", WITHIN, ("script.kinds",)),
    Edge("core.fixed_targets", WITHIN, ("script.kinds",)),
    Edge("core.inference_dags", WITHIN, ("script.kinds",)),
    Edge("authoring.lint.exit_status", WITHIN, ("script.kinds",)),
    Edge("authoring.lint.experiment_environment_reference", WITHIN, ("script.kinds",)),
    Edge("authoring.lint.placeholders", WITHIN, ("script.kinds",)),
    Edge("testbed.script_kind", EQUALS, ("script.kinds",)),
    # ---- the GUI ----
    Edge("gui.steps", DERIVED, ("steps",)),
    Edge("gui.review_steps", DERIVED, ("review.steps",)),
    Edge("gui.run_operations", DERIVED, ("run.operations",)),
    Edge("gui.audit", DERIVED, ("ree.audit",)),
    Edge("gui.receipts", DERIVED, ("ree.receipts",)),
    Edge("gui.receipt_operations", DERIVED, ("ree.receipts",)),
    Edge("gui.script_kinds", DERIVED, ("script.kinds",)),
    Edge(
        "gui.lint_names",
        DERIVED,
        ("gui.steps", "gui.run_operations", "gui.audit", "gui.receipts", "gui.receipt_operations", "gui.script_kinds"),
    ),
    Edge("gui.receipt_operations", EQUALS, ("spec.receipts",)),
    Edge("gui.dock_steps", WITHIN, ("gui.steps",)),
    Edge("gui.dock_step_defaults", EQUALS, ("gui.dock_steps",)),
    Edge("gui.workspace_refresh_steps", WITHIN, ("gui.dock_steps",)),
    *(
        Edge(f"gui.dock_steps.{name}", EQUALS, ("gui.dock_steps",))
        for name in ("params", "run_params", "run_requests", "requirements", "planners")
    ),
    Edge("gui.step_pages", WITHIN, ("gui.steps",)),
    Edge("gui.fixed_declarations", WITHIN, ("ree.definition",)),
    Edge("gui.page_receipts", WITHIN, ("gui.receipt_operations",)),
    Edge("gui.receipt_labels", EQUALS, ("gui.receipt_operations",)),
    Edge("gui.run_hud_tabs", WITHIN, ("gui.run_operations",)),
    Edge("gui.review_subjects", EQUALS, ("gui.review_steps",)),
    Edge("gui.inference_kinds", WITHIN, ("gui.script_kinds",)),
    Edge("gui.lint_kinds", WITHIN, ("gui.script_kinds",)),
)

IGNORED = (
    Ignored("protocol:/$defs/InitRee/properties", "an output's fields: the REE it initialized, and its name"),
    Ignored(
        "core/src/repo2ree_core/domain/ree/steps.py::REE_STEPS.requires",
        "one step's prerequisites, typed by the step key",
    ),
)

GRAPH = Graph(roots=OPERATIONS, vocabularies=VOCABULARIES, edges=EDGES, ignored=IGNORED)
