# exporters/

Pure functions `AdminGraph -> str` (or a `networkx` graph). They never touch
Django; they only read the graph, so they work on graphs loaded with
`AdminGraph.from_dict`.
