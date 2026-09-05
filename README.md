# WikiReach

WikiReach is a synchronous Python library for exploring outgoing relationships
in Wikidata.

## Installation

```bash
python -m pip install wikireach
```

For local development:

```bash
python -m pip install -e ".[dev]"
```

## API overview

```python
from wikireach import WikiReach

wiki = WikiReach()

wiki.search("Albert Einstein")       # Best matching Entity
wiki.entity("Q937")                  # Entity by Q-ID
wiki.claims("Q937")                  # Typed Claim objects grouped by P-ID
wiki.relations("Q937")               # Outgoing Relation objects
wiki.neighbors("Q937")               # Unique outgoing Entity objects
wiki.traverse("Q937", depth=2)       # TraversalResult
wiki.path("Q937", "Q5")             # Shortest outgoing PathResult
wiki.connections("Q937", "Q7186")   # Shared outgoing Connection objects
```

Search and direct lookup:

```python
entity = wiki.search("Albert Einstein")
print(entity.id, entity.label)  # Q937 Albert Einstein
```

Inspect typed claims without parsing Wikidata's raw response structure:

```python
claim = wiki.claims("Q937")["P569"][0]
print(claim.property_id, claim.value, claim.value_type)
```

Limit graph operations to Wikidata property IDs, which define allowed edge
types:

```python
neighbors = wiki.neighbors("Q937", properties={"P19", "P106"})
```

Resolve labels when displaying relations:

```python
for relation in wiki.relations("Q937", resolve_labels=True):
    print(relation.property_label, "->", relation.target_label)
```

Find direct shared targets:

```python
for connection in wiki.connections("Q937", "Q7186", properties={"P106", "P166"}):
    print(connection.entity.label)
```

## Unsupported features

WikiReach currently does not support incoming relations, SPARQL, caching,
asynchronous requests, Wikipedia content, weighted paths, or arbitrary graph
algorithms.

## Development

```bash
pytest
ruff check .
mypy .
```

The package targets Python 3.11 and later.
