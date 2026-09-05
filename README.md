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

## Use names or Q-IDs

Entity-facing APIs accept an ordinary search phrase or an explicit Wikidata Q-ID.
Names resolve to the best English Wikidata search result.

```python
from wikireach import WikiReach

wiki = WikiReach()

einstein = wiki.entity("Albert Einstein")
print(einstein.id, einstein.label)
# Q937 Albert Einstein

print(
    [
        entity.label
        for entity in wiki.neighbors("Albert Einstein", properties={"P19", "P106"})
    ]
)
# ['Ulm', 'physicist', ...]
```

Use Q-IDs when your program requires an unambiguous entity:

```python
wiki.entity("Q937")
```

## API overview

```python
from wikireach import WikiReach

wiki = WikiReach()

wiki.search("Albert Einstein")  # Best matching Entity
wiki.entity("Albert Einstein")  # Entity by name or Q-ID
wiki.property("P31")  # Property metadata by P-ID
wiki.claims("Albert Einstein")  # Typed claims grouped by P-ID
wiki.relations("Albert Einstein")  # Outgoing Relation objects
wiki.neighbors("Albert Einstein")  # Unique outgoing Entity objects
wiki.traverse("Albert Einstein", depth=2)  # TraversalResult
wiki.path("Albert Einstein", "human")  # Shortest outgoing PathResult
wiki.connections("Albert Einstein", "Marie Curie")  # Shared outgoing Connection objects
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

Claims can also carry contextual qualifier values. They remain grouped by their
Wikidata property ID and use the same typed value models as a claim's main value:

```python
claim = wiki.claims("Q937")["P166"][0]
for property_id, values in claim.qualifiers.items():
    print(property_id, values)
```

Look up the readable metadata behind a property ID:

```python
property_ = wiki.property("P31")
print(property_.label, property_.datatype)
# instance of wikibase-item
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
