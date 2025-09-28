"""Compatibility wrapper for the archived ETL importer.

Historically the bulk importer lived at :mod:`scripts.etl_seed`. When the
project reorganised its tooling, the implementation moved to
``legacy/etl/etl_seed.py``.  A hard failure here made it easy for humans to
discover the new location, but the automated test-suite – and a handful of
ancillary scripts – still import from the old path.

To keep that surface stable we now proxy the public API back to the archived
module.  The underlying code continues to live in the ``legacy`` package so we
avoid a wholesale rewrite, while callers (tests included) can continue to use
``scripts.etl_seed`` without adjustments.
"""

from legacy.etl.etl_seed import *  # type: ignore F403,F401

__all__ = [name for name in globals() if not name.startswith("_")]
