"""New package skeleton for incremental migration.

This module re-exports symbols as layers are copied from
`cradle_selrena_core`.  During migration callers can import from either
package; old code will continue working until the final renaming.
"""

from . import domain as _domain
from . import application as _application
from . import schemas as _schemas
from . import inference as _inference
from . import utils as _utils
from . import adapters as _adapters
from . import ports as _ports

# expose commonly used classes at package level for convenience
__all__: list[str] = [
    # domain
    *_domain.__all__,
    # application
    *_application.__all__,
    # schemas
    *[_ for _ in _schemas.__all__],
    # inference
    *_inference.__all__,
    # utils
    *_utils.__all__,
    # adapters
    *_adapters.__all__,
    # ports
    *_ports.__all__,
]
