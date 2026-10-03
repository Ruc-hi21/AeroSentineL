"""Typed errors with stable codes the dashboard can switch on."""


class AeroSentinelError(Exception):
    """Base class for all AeroSentinel errors. code is a stable string the UI can switch on."""
    code = "INTERNAL_ERROR"

    def __init__(self, message):
        super().__init__(message)
        self.message = message

    def __repr__(self):
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"

    def to_dict(self) -> dict:
        """Serialize error details to a dictionary structure for UI and API consumption."""
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
        }


class InvalidDataError(AeroSentinelError):
    """Raised when the uploaded dataset is missing columns or is unparseable."""
    code = "INVALID_DATASET"


class ProcessingError(AeroSentinelError):
    """Raised when preprocessing (cleaning/health/features) fails unexpectedly."""
    code = "PROCESSING_FAILED"


class PredictionError(AeroSentinelError):
    """Raised when both RUL and risk prediction stages fail simultaneously."""
    code = "PREDICTION_FAILED"


class ModelNotFoundError(AeroSentinelError):
    """Raised when a requested model version has not been trained yet."""
    code = "MODEL_UNAVAILABLE"
