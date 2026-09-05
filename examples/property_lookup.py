# Look up a Wikidata property by P-ID.

import sys

from wikireach import WikiReach

property_id = sys.argv[1] if len(sys.argv) > 1 else "P31"
property_ = WikiReach().property(property_id)

print(f"{property_.id}: {property_.label}")
print(f"Datatype: {property_.datatype}")
print(f"Description: {property_.description}")
