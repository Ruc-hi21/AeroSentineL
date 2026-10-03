"""Typed errors with stable codes the dashboard can switch on."""


class AeroSentinelError(Exception):
    """Base class for all AeroSentinel errors. code is a stable string the UI can switch on."""
    code = "INTERNAL_ERROR"

    def __init__(self, message):
        super().__init__(message)
        self.message = message

    def __repr__(self):
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class InvalidDataError(AeroSentinelError):
    """Raised when the uploaded dataset is missing columns or is unparseable."""
    code = "INVALID_DATASET"


class ProcessingError(AeroSentinelError):
    code = "PROCESSING_FAILED"


class PredictionError(AeroSentinelError):
    code = "PREDICTION_FAILED"


class ModelNotFoundError(AeroSentinelError):
    code = "MODEL_UNAVAILABLE"
