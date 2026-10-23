# examples/

```bash
python examples/quickstart/manage.py admin_graph --format mermaid --app library
python examples/quickstart/manage.py admin_graph -o graph.json
python examples/consume_graph.py graph.json   # reads the JSON without Django
```

`quickstart/manage.py` runs the bundled test project from a source checkout.
