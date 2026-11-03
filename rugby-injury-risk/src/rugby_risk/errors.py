class SourceNotAuthorizedError(Exception):
    """A source has not been authorized for collection."""


class ParseError(Exception):
    """Source content could not be parsed."""


class QualityCheckError(Exception):
    """A data quality check failed."""


class LeakageError(Exception):
    """A temporal data leakage was detected."""


class PrivacyViolationError(Exception):
    """A privacy safeguard was violated."""
