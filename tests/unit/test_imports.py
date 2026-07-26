"""Every module in the package must at least import — stubs included."""

import importlib
import pkgutil

import scalpbot


def test_all_modules_import():
    failures = []
    for mod in pkgutil.walk_packages(scalpbot.__path__, prefix="scalpbot."):
        try:
            importlib.import_module(mod.name)
        except Exception as exc:  # noqa: BLE001
            failures.append((mod.name, repr(exc)))
    assert not failures, f"unimportable modules: {failures}"
