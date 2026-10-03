"""Typed errors with stable codes the dashboard can switch on."""


class AeroSentinelError(Exception):
    code = "INTERNAL_ERROR"

    def __init__(self, message):
        super().__init__(message)
        self.message = message

    def __repr__(self):
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class InvalidDataError(AeroSentinelError):
    code = "INVALID_DATASET"


class ProcessingError(AeroSentinelError):
    code = "PROCESSING_FAILED"


class PredictionError(AeroSentinelError):
    code = "PREDICTION_FAILED"


class ModelNotFoundError(AeroSentinelError):
    code = "MODEL_UNAVAILABLE"
