"""Domain errors. Services raise these; the API layer maps them to HTTP responses.
Services never import the web framework."""


class AppError(Exception):
    status_code = 400
    code = "error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.code)
        self.message = message or self.code


class AuthenticationFailed(AppError):
    status_code = 401
    code = "authentication_failed"


class PermissionDenied(AppError):
    status_code = 403
    code = "permission_denied"


class NotFound(AppError):
    """Also used when a place exists but is outside the caller's jurisdiction (404, never 403)."""

    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class DuplicateSuspect(Conflict):
    """A place already exists within the duplicate-guard radius."""

    code = "duplicate_suspect"


class InvalidInput(AppError):
    status_code = 422
    code = "invalid_input"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"


class AccountLocked(AppError):
    status_code = 429
    code = "locked"
