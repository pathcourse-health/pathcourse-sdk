"""Exceptions for the PathCourse SDK."""


class PathCourseError(Exception):
    """Base exception for all PathCourse SDK errors."""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AuthenticationError(PathCourseError):
    """Raised when the API key is missing or invalid."""
    pass


class RateLimitError(PathCourseError):
    """Raised when the rate limit is exceeded."""
    pass


class InsufficientBalanceError(PathCourseError):
    """Raised when the agent's USDC balance is too low (HTTP 402)."""
    pass


class ForbiddenError(PathCourseError):
    """Generic HTTP 403 — access denied. See .response dict for details."""
    pass


class ModelNotInTierError(ForbiddenError):
    """The requested model is not available for the agent's cert tier."""
    pass


class NotFoundError(PathCourseError):
    """Generic HTTP 404 — resource not found. See .response dict for details."""
    pass


class ModelNotFoundError(NotFoundError):
    """The requested model does not exist."""
    pass


class InferenceUnavailableError(PathCourseError):
    """Raised when a CPU-native model's sidecar is not available (HTTP 503)."""
    pass


class GatewayError(PathCourseError):
    """Raised for unexpected gateway-side errors."""
    pass
