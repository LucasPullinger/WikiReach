
# WikiReach

WikiReach is a Python library for exploring and traversing relationships in Wikidata.

The project aims to provide a simple Python interface for working with Wikidata entities, properties, and relationships without requiring users to work directly with raw Wikidata API responses or SPARQL for common graph operations.

## Status

WikiReach is in early development.

The first release supports English-language Wikidata entity search.

## Planned Features

WikiReach will focus on graph-based exploration of Wikidata.

Planned features include:

* Search for Wikidata entities by name
* Fetch entities by Wikidata ID
* Access clean entity metadata
* Resolve Wikidata property and entity labels
* Represent relationships between entities
* Find neighbouring entities
* Traverse relationships to a configurable depth
* Find paths between two entities
* Find shared connections between entities
* Filter traversal by Wikidata property
* Cache repeated Wikidata requests

The library will focus on Wikidata relationship traversal rather than general Wikipedia content access.

## Example

```python
from wikireach import WikiReach

wiki = WikiReach()

entity = wiki.search("Albert Einstein")

print(entity.id)          # Q937
print(entity.label)       # Albert Einstein
print(entity.description) # German-born theoretical physicist
```

Look up a known entity directly by its Wikidata Q-ID:

```python
entity = wiki.entity("Q937")

print(entity.label)  # Albert Einstein
```

Fetch raw claim values, grouped by Wikidata property ID:

```python
claims = wiki.claims("Q937")

print(claims["P31"])  # [{"entity-type": "item", "numeric-id": 5, "id": "Q5"}]
```

Claims marked by Wikidata as having an unknown or no value are represented as
`None`.

Convert item-valued claims into typed relationships:

```python
for relation in wiki.relations("Q937"):
    print(relation.property_id, relation.target_id)

# P31 Q5
# P19 Q1731
# P106 Q169470
```

Relations are ID-only by default. Resolve English labels when displaying them:

```python
for relation in wiki.relations("Q937", resolve_labels=True):
    print(
        f"{relation.property_label or relation.property_id} -> "
        f"{relation.target_label or relation.target_id}"
    )

# instance of -> human
# place of birth -> Ulm
```

Get the directly connected entities as `Entity` objects:

```python
for entity in wiki.neighbors("Q937"):
    print(entity.id, entity.label)

# Q1860 English
# Q188 German
# Q3012 Ulm
```

Limit graph operations to selected Wikidata property IDs, which define the
allowed edge types:

```python
wiki.neighbors(
    "Q937",
    properties={"P19", "P106"},
)
```

Traverse outward through item-to-item relations with breadth-first search:

```python
result = wiki.traverse("Q937", depth=2)

print(result.root)
print(len(result.entities))
print(len(result.relations))
```

Find the shortest outgoing relationship path between two entities:

```python
path = wiki.path("Q937", "Q13133")

for entity in path.entities:
    print(entity.id, entity.label)
```

## Requirements

* Python 3.11 or later

## Development Installation

Clone the repository and create a virtual environment:

```bash
python -m venv .venv
```

Activate the environment.

On macOS and Linux:

```bash
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

Install WikiReach in editable mode with the development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Editable installation allows changes in `src/wikireach` to apply without reinstalling the package.

## Project Structure

```text
.
├── .gitignore
├── LICENSE
├── README.md
├── pyproject.toml
├── src/
│   └── wikireach/
│       ├── __init__.py
│       ├── client.py
│       ├── entity.py
│       ├── exceptions.py
│       └── relation.py
└── tests/
    ├── test_client.py
    └── test_import.py
```

The project uses a `src` layout. The `wikireach` package lives inside `src/wikireach`.

## Development Commands

Run the test suite:

```bash
pytest
```

Run Ruff:

```bash
ruff check .
```

Run mypy:

```bash
mypy .
```

Run all checks before committing changes:

```bash
pytest
ruff check .
mypy .
```

## Design Goals

WikiReach should provide a small and predictable public API.

The library should:

* Hide unnecessary Wikidata API response structure
* Use clear Python objects for entities and relationships
* Preserve Wikidata IDs when they are useful
* Use type hints throughout the public API
* Avoid unnecessary dependencies
* Keep network access separate from entity models
* Support testing without requiring live Wikidata requests

WikiReach should not attempt to replace the full Wikidata API or SPARQL.

Users who need complex data queries should continue to use Wikidata Query Service or the official APIs directly.

## Development Roadmap

### 0.1

Initial Wikidata access:

* Entity search
* Entity model
* Basic API client
* Error handling
* Tests using mocked HTTP requests

### 0.2

Relationship support:

* Fetch entity claims
* Resolve property labels
* Resolve related entity labels
* Relation model
* Entity neighbours

### 0.3

Graph traversal:

* Configurable traversal depth
* Path finding
* Property filtering
* Shared connections

### Later

Possible future work includes:

* Request caching
* Async API support
* Additional graph algorithms
* Wikipedia page metadata
* Command-line tools

## Contributing

WikiReach is currently in early development.

Issues and pull requests are welcome as the public API develops.

Before submitting changes, run:

```bash
pytest
ruff check .
mypy .
```

## License

WikiReach uses the MIT License. See `LICENSE` for details.
