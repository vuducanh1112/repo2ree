// Minimal, dependency-free theme for repo2ree presentations.

#let ink = rgb("#0f172a")
#let muted = rgb("#475569")
#let canvas = rgb("#f8fafc")

#let deck(body) = {
  set page(width: 13.333in, height: 7.5in, margin: 0pt, fill: canvas)
  set text(font: "DejaVu Sans", size: 22pt, fill: ink)
  set par(leading: 0.72em)
  set list(spacing: 13pt)
  body
}

#let slide(title, body, author: "Your name", event: "Event", date: "YYYY-MM-DD") = {
  box(width: 100%, height: 100%)[
    #place(top + left)[
      #rect(
        width: 100%,
        height: 42pt,
        fill: none,
        stroke: (bottom: 1pt + rgb("#cbd5e1")),
      )[
        #box(width: 100%, height: 100%, inset: (x: 58pt))[
          #align(left + horizon)[
            #grid(
              columns: (1fr, auto),
              gutter: 24pt,
              align: (left + horizon, right + horizon),
              text(size: 11pt, weight: "bold", fill: ink)[#title],
              image("../assets/nfdixcs-logo.png", height: 20pt),
            )
          ]
        ]
      ]
    ]

    #box(
      width: 100%,
      height: 100%,
      inset: (left: 58pt, right: 58pt, top: 108pt, bottom: 70pt),
    )[#body]

    #place(bottom + left)[
      #rect(width: 100%, height: 42pt, fill: ink)[
        #box(width: 100%, height: 100%, inset: (x: 58pt))[
          #align(left + horizon)[
            #grid(
              columns: (1fr, auto, auto, auto),
              gutter: 22pt,
              text(size: 11pt, weight: "bold", fill: white)[#author],
              text(size: 11pt, fill: white)[#date],
              text(size: 11pt, fill: white)[#event],
              text(size: 11pt, weight: "bold", fill: white)[
                #context counter(page).display()
              ],
            )
          ]
        ]
      ]
    ]
  ]
  pagebreak(weak: true)
}
