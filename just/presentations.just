PRESENTATION_DIST_DIR := "dist/presentations"
TYPST_OVERVIEW_SOURCE := "presentations/typst/repo2ree-overview/slides.typ"
TYPST_OVERVIEW_PDF := PRESENTATION_DIST_DIR + "/repo2ree-overview.pdf"

# Build every presentation artifact.
[group('Presentations')]
build-presentations: build-typst-presentations

# Build all Typst decks.
[group('Presentations')]
build-typst-presentations:
    mkdir -p {{ PRESENTATION_DIST_DIR }}
    typst compile --root . {{ TYPST_OVERVIEW_SOURCE }} {{ TYPST_OVERVIEW_PDF }}

# Rebuild the overview PDF whenever its Typst sources or referenced assets change.
[group('Presentations')]
watch-typst-overview:
    mkdir -p {{ PRESENTATION_DIST_DIR }}
    typst watch --root . {{ TYPST_OVERVIEW_SOURCE }} {{ TYPST_OVERVIEW_PDF }}
