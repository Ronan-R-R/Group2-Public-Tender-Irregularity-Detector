import importlib

import pytest


@pytest.mark.parametrize("package", ["api", "db", "detection", "ingestion"])
def test_package_imports_from_src_layout(package: str) -> None:
    module = importlib.import_module(package)
    assert module.__file__ is not None
    assert "src" in module.__file__
