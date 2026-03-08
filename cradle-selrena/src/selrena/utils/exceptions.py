class SelrenaError(Exception):
    """Base exception for Selrena core modules."""


class ConfigurationError(SelrenaError):
    """Raised when configuration is invalid or missing."""""