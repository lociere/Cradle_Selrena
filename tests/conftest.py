from pathlib import Path
import sys

# Ensure the Python package source is on sys.path for pytest runs.
# This lets tests import the `selrena` package from
# core/cradle-selrena-core/src without installing the package.
repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "core" / "cradle-selrena-core" / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))
else:
    # Fallback: maybe package is at repo root /src
    alt = repo_root / "src"
    if alt.exists():
        sys.path.insert(0, str(alt))
