"""Compatibility shim for running FastAPI/pydantic on Python 3.14 release candidates.

pydantic 2.13 calls ``typing._eval_type(..., prefer_fwd_module=True)``, a keyword argument that
only exists in the *final* CPython 3.14.0 release. On 3.14.0rcN the stdlib ``typing._eval_type``
lacks that parameter, so importing FastAPI raises ``TypeError``. This shim wraps
``typing._eval_type`` to silently drop the unknown keyword when the running interpreter does not
support it. It is a no-op on Python versions where the parameter already exists.

Import this module *before* importing FastAPI/pydantic.
"""

from __future__ import annotations

import inspect
import typing


def apply() -> None:
    original = typing._eval_type  # type: ignore[attr-defined]
    try:
        params = inspect.signature(original).parameters
    except (TypeError, ValueError):  # pragma: no cover - defensive
        params = {}
    if "prefer_fwd_module" in params or getattr(original, "_pipeline_patched", False):
        return

    def patched(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.pop("prefer_fwd_module", None)
        return original(*args, **kwargs)

    patched._pipeline_patched = True  # type: ignore[attr-defined]
    typing._eval_type = patched  # type: ignore[attr-defined]


apply()
