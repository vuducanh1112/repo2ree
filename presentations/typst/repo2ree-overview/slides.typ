#import "../theme/repo2ree.typ": *

#show: deck

#let author = "Name"
#let event = "Plenary Meeting"

#let page(title, body) = slide(
  title,
  author: author,
  event: event,
  date: "YYYY-MM-DD",
  body,
)

#page("Why research software is hard to rerun")[
  - Which source revision produced the result?
  - Which compiler, system libraries, and transitive dependencies were present?
  - Which command and arguments did the author run?
  - What output counts as success?
  - Will it still run if a registry or hosting service disappears?
]

#page("What is an REE?")[
  #text(size: 27pt, weight: "bold")[
    A Reproducible Execution Environment is a portable description of a
    computational result.
  ]

  #v(30pt)
  #grid(
    columns: (1fr, 1fr, 1fr),
    gutter: 36pt,
    align: center,
    [*Source*\ Exact revision],
    [*Runtime*\ Rebuild recipe],
    [*Experiment*\ Command and check],
  )

  #v(34pt)
  #text(size: 20pt, fill: muted)[
    Declarations say what should run. Receipts and result baselines record what
    did run. A sealed bundle carries both, plus a standalone reproducer.
  ]
]

#page("Federated compute architecture")[
  #align(center)[
    #image(
      "../../../docs/public/reference/architecture/assets/federated-compute.svg",
      height: 300pt,
      fit: "contain",
    )
  ]
]
