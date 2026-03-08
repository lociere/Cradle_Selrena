Selrena — core package and compatibility layer.

This distribution exposes the `selrena` top-level Python package. All
internal modules have been migrated from the earlier ``cradle_selrena`` and
``cradle_selrena_core`` names. A small compatibility shim remains both at the top level and inside
``selrena/cradle_selrena_core`` to provide ``cradle_selrena_core`` imports
with a ``DeprecationWarning``. The old ``cradle_selrena`` package has been
removed; code should import directly from ``selrena`` going forward.

When migrating existing projects, update imports accordingly, and install
the new package name. 
