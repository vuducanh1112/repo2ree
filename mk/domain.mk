# Generated views of the domain model, derived from the rules that define it.
#
# The sibling of architecture.mk and journals.mk, and the third question in the
# set: those draw what the code imports and what a run did, this draws what the
# REE *is* — which evidence rests on which, and what stops being true when a
# step is re-run. Read out of domain/ree/audit.py rather than maintained here,
# so a comparison added to a step adds an edge to the picture.

.PHONY: evidence-graph

# Shared with architecture.mk, and restated with ?= so this file stands on its
# own regardless of include order. Gitignored either way: a generated view is
# not a file to review in a diff.
DIAGRAM_DIR ?= dist/diagrams

# The audit rules the diagram is derived from. Named so the target can depend on
# it: the graph is a pure function of this file, so make can skip the render
# when it has not moved.
AUDIT_RULES = core/src/repo2ree_core/domain/ree/audit.py

EVIDENCE_GRAPH = $(DIAGRAM_DIR)/evidence.svg

evidence-graph: $(EVIDENCE_GRAPH)

$(EVIDENCE_GRAPH): $(AUDIT_RULES) scripts/evidence_graph.py
	@mkdir -p $(DIAGRAM_DIR)
	python scripts/evidence_graph.py -o $@
