# Basic package import tests.

import wikireach


def test_package_imports() -> None:
    # The package can be imported.
    assert wikireach.__version__ == "0.1.0"
