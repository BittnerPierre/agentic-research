"""Compatibility package that aliases the existing src/ layout."""

from importlib import import_module

_src = import_module("src")
__path__ = _src.__path__
__all__ = []

for _name in dir(_src):
    if _name.startswith("_"):
        continue
    globals()[_name] = getattr(_src, _name)
    __all__.append(_name)
